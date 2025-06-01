import os
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv

from staarb.clients import MockClient
from staarb.core.bus.event_bus import EventBus
from staarb.core.bus.events import (
    MarketDataEvent,
    SessionEvent,
)
from staarb.core.bus.subscribers import setup_backtest_subscribers
from staarb.core.enums import SessionType
from staarb.core.types import DataRequest
from staarb.data.exchange_info_fetcher import BinanceExchangeInfo
from staarb.data.ohlc_fetcher import MarketDataFetcher
from staarb.persistence.storage import TradingStorage
from staarb.portfolio.portfolio import Portfolio
from staarb.strategy import StatisticalArbitrage
from staarb.trader.order_executor import OrderExecutor
from staarb.utils import async_cmd, date_to_milliseconds


def _setup_backtest_environment(
    env_file: str | None, api_key: str | None, api_secret: str | None
) -> tuple[str, str]:
    """
    Set up the backtest environment by loading API keys and other configurations.

    Args:
        env_file: Path to the environment file.
        api_key: Binance API key.
        api_secret: Binance API secret key.

    Returns:
        A tuple containing the API key and API secret.

    Raises:
        click.ClickException: If API keys are not found.
    """
    if env_file and Path(env_file).exists():
        load_dotenv(dotenv_path=env_file)
        click.echo(f"Loaded environment variables from {env_file}")
    elif env_file:
        click.echo(f"Warning: Environment file {env_file} not found. Checking default locations.")

    # Load default .env if it exists and no specific env_file was provided or found
    if not env_file or (env_file and not Path(env_file).exists()):
        load_dotenv()

    # Retrieve API keys from environment if not provided directly
    api_key = api_key or os.getenv("BINANCE_API_KEY")
    api_secret = api_secret or os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        raise click.ClickException(
            "API key and secret must be provided either via command line, environment variables, or an .env file."
        )
    return api_key, api_secret


async def _initialize_backtest_components(  # noqa: PLR0913
    symbols: list[str],
    start_date: datetime,
    end_date: datetime,
    interval: str,
    train_val_split: float,
    entry_threshold: float,
    exit_threshold: float,
    api_key: str,
    api_secret: str,
) -> tuple[MockClient, Portfolio, StatisticalArbitrage, int, int]:
    """
    Initializes and configures components required for a backtest session.

    Args:
        symbols: List of trading symbols.
        start_date: Start date of the backtest period.
        end_date: End date of the backtest period.
        interval: Time interval for k-line data.
        train_val_split: Training/validation split ratio.
        entry_threshold: Entry threshold for the strategy.
        exit_threshold: Exit threshold for the strategy.
        api_key: Binance API key.
        api_secret: Binance API secret key.

    Returns:
        A tuple containing the initialized client, portfolio, strategy,
        start time (ms), and end time (ms).
    """
    start_time = date_to_milliseconds(start_date)
    end_time = date_to_milliseconds(end_date)

    client = await MockClient.create(
        symbols,
        DataRequest(interval, start_time, end_time),
        balance={"USDC": 1000},  # TODO: Make balance configurable
        api_key=api_key,
        api_secret=api_secret,
    )

    portfolio_name = f"Backtest {','.join(symbols)}"
    portfolio = Portfolio(name=portfolio_name, client=client)
    await BinanceExchangeInfo.fetch_exchange_info(client=client)
    for symbol in symbols: # Using a loop for clarity if more operations per symbol are needed later
        portfolio.add_symbol(symbol)

    train_window_end_time = int(start_time + (end_time - start_time) * train_val_split)
    train_window = DataRequest(interval, start_time, train_window_end_time)

    train_data = await MarketDataFetcher.fetch_multiple_klines(
        client, symbols=symbols, request=train_window
    )

    strategy = StatisticalArbitrage(
        interval, entry_threshold=entry_threshold, exit_threshold=exit_threshold
    )
    strategy.fit(train_data)

    return client, portfolio, strategy, start_time, end_time


async def _run_backtest_loop(  # noqa: PLR0913
    client: MockClient,
    strategy: StatisticalArbitrage,
    portfolio: Portfolio,
    storage_url: str,
    save: bool,
    start_date: datetime,
    end_date: datetime,
    symbols: list[str],
    train_val_split: float,
):
    """
    Runs the main backtesting event loop.

    Args:
        client: The initialized MockClient.
        strategy: The fitted StatisticalArbitrage strategy.
        portfolio: The initialized Portfolio.
        storage_url: URL for the storage backend.
        save: Boolean indicating whether to save session results.
        start_date: Start date of the backtest period (for session saving).
        end_date: End date of the backtest period (for session saving).
        symbols: List of trading symbols (for calculating cur_pt).
        train_val_split: Training/validation split ratio (for calculating cur_pt).
    """
    storage = None
    if save:
        storage = TradingStorage(storage_url)
        await storage.save_session(
            SessionEvent(
                session_type=SessionType.BACKTEST,
                start_time=start_date,
                end_time=end_date,
            )
        )

    order_executor = OrderExecutor(client=client)
    setup_backtest_subscribers(strategy, portfolio, order_executor, storage)

    click.echo("Starting backtest event loop...")

    if symbols and strategy.fitted_on_symbols and client.ohlcv_data:
        # Calculate cur_pt based on the length of the full dataset loaded into the client
        # and the train_val_split ratio.
        # This assumes ohlcv_data is populated by MockClient.create for the entire period.
        first_symbol_data_length = len(client.ohlcv_data[symbols[0]])
        cur_pt = int(first_symbol_data_length * train_val_split)
        client.set_current_pointer(cur_pt)
        click.echo(f"Client pointer set to index {cur_pt} for mock data iteration.")
    elif not client.ohlcv_data:
        click.echo("Warning: client.ohlcv_data is not populated. Cannot set current pointer accurately.", err=True)
    else:
        click.echo("Warning: No symbols or strategy not fitted. Market data iteration might be incorrect.", err=True)

    for market_data in client.get_mock_data(strategy.get_lookback_request()):
        await EventBus.publish(MarketDataEvent, data=MarketDataEvent(data=market_data))
    click.echo("Backtest event loop completed.")


@click.command()
@click.argument("symbols", nargs=-1)
@click.argument("start_date", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.argument("end_date", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--interval", default="1d", help="Time interval for the backtest (default: 1d).")
@click.option(
    "--train-val-split", default=0.8, type=float, help="Train/validation split ratio (default: 0.8)."
)
@click.option("--entry-threshold", default=1.0, type=float, help="Entry threshold for the strategy.")
@click.option("--exit-threshold", default=0.0, type=float, help="Exit threshold for the strategy.")
@click.option(
    "--env-file",
    default=None,
    type=click.Path(),
    help="Path to the environment file for configuration.",
)
@click.option("--api-key", envvar="BINANCE_API_KEY", help="Binance API key.")
@click.option("--api-secret", envvar="BINANCE_API_SECRET", help="Binance API secret key.")
@click.option("--save/--no-save", default=True, help="Save backtest results for dashboard analysis.")
@click.option(
    "--storage-url", default="sqlite:///trading_data.db", help="URL for the storage backend (optional)."
)
@async_cmd
async def backtest(  # noqa: PLR0913
    symbols: list[str],
    start_date: datetime,
    end_date: datetime,
    interval: str,
    train_val_split: float,
    entry_threshold: float,
    exit_threshold: float,
    env_file: str | None,
    api_key: str | None,
    api_secret: str | None,
    *,
    save: bool,
    storage_url: str,
):
    """Run a backtest for the given SYMBOLS between START_DATE and END_DATE."""
    api_key_resolved, api_secret_resolved = _setup_backtest_environment(env_file, api_key, api_secret)

    click.echo(f"Running backtest for symbols: {', '.join(symbols)}")
    click.echo(f"Start date: {start_date}, End date: {end_date}, Interval: {interval}")

    client = None  # Initialize client to None for the finally block
    try:
        # Initialize components
        client, portfolio, strategy, _, _ = await _initialize_backtest_components(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            train_val_split=train_val_split,
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            api_key=api_key_resolved,
            api_secret=api_secret_resolved,
        )

        # Run the backtest loop
        await _run_backtest_loop(
            client=client,
            strategy=strategy,
            portfolio=portfolio,
            storage_url=storage_url,
            save=save,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            train_val_split=train_val_split,
        )

    except Exception as e:
        msg = f"An error occurred during backtest: {e}"
        # The finally block will handle client connection closing.
        raise click.ClickException(msg) from e
    finally:
        if client is not None:
            await client.close_connection()
            click.echo("Client connection closed.")

    click.echo("Backtest completed successfully.")
