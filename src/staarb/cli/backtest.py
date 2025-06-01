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
    click.echo(f"Running backtest for symbols: {', '.join(symbols)}")

    # Load environment file if provided and exists
    if env_file and Path(env_file).exists():
        load_dotenv(dotenv_path=env_file)
    elif env_file:
        click.echo(f"Warning: Environment file {env_file} not found. Continuing without it.")

    load_dotenv()  # Load default .env if exists

    api_key = api_key or os.getenv("BINANCE_API_KEY")
    api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        click.echo("API key and secret must be provided either via command line or environment variables.")
        return
    click.echo(f"Start date: {start_date}, End date: {end_date}, Interval: {interval}")
    start_time = date_to_milliseconds(start_date)
    end_time = date_to_milliseconds(end_date)

    try:
        ######## Create a mock client for backtesting ########
        client = await MockClient.create(
            symbols,
            DataRequest(interval, start_time, end_time),
            balance={"USDC": 1000},
            api_key=api_key,
            api_secret=api_secret,
        )

        portfolio_name = f"Backtest {','.join(symbols)}"
        portfolio = Portfolio(name=portfolio_name, client=client)
        await BinanceExchangeInfo.fetch_exchange_info(client=client)
        [portfolio.add_symbol(symbol) for symbol in symbols]
        train_window = DataRequest(
            interval, start_time, int(start_time + (end_time - start_time) * train_val_split)
        )
        train_data = await MarketDataFetcher.fetch_multiple_klines(
            client, symbols=symbols, request=train_window
        )
        strategy = StatisticalArbitrage(
            interval, entry_threshold=entry_threshold, exit_threshold=exit_threshold
        )
        strategy.fit(train_data)
        ######## End of mock client creation ########

        ######## Start the backtest session ########
        if save:
            storage = TradingStorage(storage_url)
            await storage.save_session(
                SessionEvent(
                    session_type=SessionType.BACKTEST,
                    start_time=start_date,
                    end_time=end_date,
                )
            )
        else:
            storage = None
        order_executor = OrderExecutor(client=client)
        setup_backtest_subscribers(strategy, portfolio, order_executor, storage)

        click.echo("Starting backtest...")
        cur_pt = int(len(train_data[symbols[0]]) * train_val_split)
        client.set_current_pointer(cur_pt)

        for market_data in client.get_mock_data(strategy.get_lookback_request()):
            await EventBus.publish(MarketDataEvent, data=MarketDataEvent(data=market_data))
        ######## End of backtest session ########
    except Exception as e:
        if "client" in locals():
            await client.close_connection()
        msg = f"An error occurred during backtest: {e}"
        raise click.ClickException(msg) from e

    await client.close_connection()
    click.echo("Backtest completed successfully.")
