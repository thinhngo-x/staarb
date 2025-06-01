import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import click
from click.testing import CliRunner

from staarb.cli.backtest import (
    backtest,
    _setup_backtest_environment,
    _initialize_backtest_components,
    _run_backtest_loop,
)
from staarb.core.types import DataRequest
from staarb.core.enums import SessionType
from staarb.core.bus.events import MarketDataEvent, SessionEvent
from staarb.clients import MockClient
from staarb.portfolio.portfolio import Portfolio
from staarb.strategy import StatisticalArbitrage


class TestSetupBacktestEnvironment:
    """Test the _setup_backtest_environment helper function."""

    def test_keys_provided_directly(self):
        api_key, api_secret = _setup_backtest_environment(None, "direct_key", "direct_secret")
        assert api_key == "direct_key"
        assert api_secret == "direct_secret"

    @patch("staarb.cli.backtest.os.getenv")
    def test_keys_from_env_vars(self, mock_getenv):
        mock_getenv.side_effect = lambda key: "env_key" if key == "BINANCE_API_KEY" else "env_secret"
        api_key, api_secret = _setup_backtest_environment(None, None, None)
        assert api_key == "env_key"
        assert api_secret == "env_secret"
        mock_getenv.assert_any_call("BINANCE_API_KEY")
        mock_getenv.assert_any_call("BINANCE_API_SECRET")

    @patch("staarb.cli.backtest.Path.exists", return_value=True)
    @patch("staarb.cli.backtest.load_dotenv")
    @patch("staarb.cli.backtest.os.getenv")
    def test_keys_from_env_file(self, mock_getenv, mock_load_dotenv, mock_path_exists):
        mock_getenv.side_effect = lambda key: "file_key" if key == "BINANCE_API_KEY" else "file_secret"
        # Simulate load_dotenv populating os.environ, which getenv then reads

        api_key, api_secret = _setup_backtest_environment("dummy.env", None, None)

        mock_path_exists.assert_called_once_with(Path("dummy.env"))
        mock_load_dotenv.assert_called_once_with(dotenv_path="dummy.env")
        assert api_key == "file_key"
        assert api_secret == "file_secret"

    @patch("staarb.cli.backtest.os.getenv")
    def test_precedence_direct_over_env(self, mock_getenv):
        mock_getenv.side_effect = lambda key: "env_key" if key == "BINANCE_API_KEY" else "env_secret"
        api_key, api_secret = _setup_backtest_environment(None, "direct_key", "direct_secret")
        assert api_key == "direct_key"
        assert api_secret == "direct_secret"
        # getenv should not be called if direct keys are provided
        mock_getenv.assert_not_called()

    @patch("staarb.cli.backtest.Path.exists", return_value=True)
    @patch("staarb.cli.backtest.load_dotenv")
    @patch("staarb.cli.backtest.os.getenv")
    def test_precedence_env_over_file(self, mock_getenv, mock_load_dotenv, mock_path_exists):
        # Env vars are read first by getenv, then load_dotenv is called if file specified
        # but actual getenv calls inside the function happen after potential load_dotenv

        # Simulate env vars already set
        mock_getenv.side_effect = lambda key, default=None: {
            "BINANCE_API_KEY": "env_key",
            "BINANCE_API_SECRET": "env_secret"
        }.get(key, default)

        api_key, api_secret = _setup_backtest_environment("dummy.env", None, None)

        mock_path_exists.assert_called_once_with(Path("dummy.env"))
        # load_dotenv IS called because an env_file is provided and exists
        mock_load_dotenv.assert_called_once_with(dotenv_path="dummy.env")

        # Even if load_dotenv was called, os.getenv will take precedence if vars are already in environment
        # The mock_getenv needs to reflect that the values are 'taken' from env
        assert api_key == "env_key"
        assert api_secret == "env_secret"


    @patch("staarb.cli.backtest.Path.exists", return_value=False) # .env file does not exist
    @patch("staarb.cli.backtest.load_dotenv") # To check if default .env load is attempted
    @patch("staarb.cli.backtest.os.getenv", return_value=None) # No env vars set
    def test_exception_if_no_keys_found(self, mock_getenv, mock_load_dotenv, mock_path_exists):
        with pytest.raises(click.ClickException) as exc_info:
            _setup_backtest_environment("nonexistent.env", None, None)
        assert "API key and secret must be provided" in str(exc_info.value)
        # Called for "nonexistent.env"
        mock_path_exists.assert_called_once_with(Path("nonexistent.env"))
        # Called for default .env
        mock_load_dotenv.assert_called_once_with()


@pytest.mark.asyncio
class TestInitializeBacktestComponents:
    """Test the _initialize_backtest_components helper function."""

    @pytest.fixture
    def start_date_dt(self):
        return datetime(2024, 1, 1)

    @pytest.fixture
    def end_date_dt(self):
        return datetime(2024, 1, 10)

    @pytest.fixture
    def common_params(self, start_date_dt, end_date_dt):
        return {
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "start_date": start_date_dt,
            "end_date": end_date_dt,
            "interval": "1d",
            "train_val_split": 0.8,
            "entry_threshold": 1.0,
            "exit_threshold": 0.0,
            "api_key": "test_key",
            "api_secret": "test_secret",
        }

    @patch("staarb.cli.backtest.date_to_milliseconds", side_effect=lambda x: int(x.timestamp() * 1000))
    @patch("staarb.cli.backtest.MockClient.create", new_callable=AsyncMock)
    @patch("staarb.cli.backtest.BinanceExchangeInfo.fetch_exchange_info", new_callable=AsyncMock)
    @patch("staarb.cli.backtest.MarketDataFetcher.fetch_multiple_klines", new_callable=AsyncMock)
    @patch("staarb.cli.backtest.Portfolio", autospec=True) # Use autospec for Portfolio
    @patch("staarb.cli.backtest.StatisticalArbitrage", autospec=True) # Use autospec for Strategy
    async def test_initialize_components_success(
        self,
        mock_strategy_class,
        mock_portfolio_class,
        mock_fetch_klines,
        mock_fetch_exchange_info,
        mock_client_create,
        mock_date_to_ms,
        common_params,
        start_date_dt,
        end_date_dt,
    ):
        mock_client_instance = AsyncMock(spec=MockClient)
        mock_client_create.return_value = mock_client_instance

        mock_portfolio_instance = MagicMock(spec=Portfolio)
        mock_portfolio_class.return_value = mock_portfolio_instance

        mock_strategy_instance = MagicMock(spec=StatisticalArbitrage)
        mock_strategy_instance.fit = MagicMock() # mock the fit method
        mock_strategy_class.return_value = mock_strategy_instance

        mock_train_data = {"BTCUSDT": [], "ETHUSDT": []}
        mock_fetch_klines.return_value = mock_train_data

        client, portfolio, strategy, start_time_ms, end_time_ms = await _initialize_backtest_components(
            **common_params
        )

        assert client == mock_client_instance
        assert portfolio == mock_portfolio_instance
        assert strategy == mock_strategy_instance
        assert start_time_ms == int(start_date_dt.timestamp() * 1000)
        assert end_time_ms == int(end_date_dt.timestamp() * 1000)

        expected_start_ms = int(start_date_dt.timestamp() * 1000)
        expected_end_ms = int(end_date_dt.timestamp() * 1000)

        mock_client_create.assert_called_once()
        args, kwargs = mock_client_create.call_args
        assert args[0] == common_params["symbols"]
        assert isinstance(args[1], DataRequest)
        assert args[1].interval == common_params["interval"]
        assert args[1].start_time == expected_start_ms
        assert args[1].end_time == expected_end_ms
        assert kwargs["balance"] == {"USDC": 1000}
        assert kwargs["api_key"] == common_params["api_key"]
        assert kwargs["api_secret"] == common_params["api_secret"]

        mock_portfolio_class.assert_called_once_with(name=f"Backtest {','.join(common_params['symbols'])}", client=mock_client_instance)
        mock_fetch_exchange_info.assert_called_once_with(client=mock_client_instance)
        assert portfolio.add_symbol.call_count == len(common_params["symbols"])
        for sym in common_params["symbols"]:
            portfolio.add_symbol.assert_any_call(sym)

        expected_train_end_ms = int(expected_start_ms + (expected_end_ms - expected_start_ms) * common_params["train_val_split"])
        mock_fetch_klines.assert_called_once()
        f_args, f_kwargs = mock_fetch_klines.call_args
        assert f_kwargs['client'] == mock_client_instance
        assert f_kwargs['symbols'] == common_params["symbols"]
        assert isinstance(f_kwargs['request'], DataRequest)
        assert f_kwargs['request'].interval == common_params["interval"]
        assert f_kwargs['request'].start_time == expected_start_ms
        assert f_kwargs['request'].end_time == expected_train_end_ms

        mock_strategy_class.assert_called_once_with(
            common_params["interval"],
            entry_threshold=common_params["entry_threshold"],
            exit_threshold=common_params["exit_threshold"],
        )
        mock_strategy_instance.fit.assert_called_once_with(mock_train_data)


@pytest.mark.asyncio
class TestRunBacktestLoop:
    """Test the _run_backtest_loop helper function."""

    @pytest.fixture
    def mock_client(self):
        client = AsyncMock(spec=MockClient)
        client.ohlcv_data = {"BTCUSDT": [MagicMock()] * 100} # 100 data points
        client.get_mock_data = MagicMock(return_value=iter([MagicMock(spec=MarketDataEvent), MagicMock(spec=MarketDataEvent)])) # Returns 2 data events
        client.set_current_pointer = MagicMock()
        return client

    @pytest.fixture
    def mock_strategy(self):
        strategy = MagicMock(spec=StatisticalArbitrage)
        strategy.get_lookback_request = MagicMock(return_value=MagicMock())
        strategy.fitted_on_symbols = True # Assume strategy is fitted
        return strategy

    @pytest.fixture
    def mock_portfolio(self):
        return MagicMock(spec=Portfolio)

    @pytest.fixture
    def common_loop_params(self, mock_client, mock_strategy, mock_portfolio):
        return {
            "client": mock_client,
            "strategy": mock_strategy,
            "portfolio": mock_portfolio,
            "storage_url": "sqlite:///test.db",
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 10),
            "symbols": ["BTCUSDT"],
            "train_val_split": 0.8,
        }

    @patch("staarb.cli.backtest.TradingStorage", autospec=True)
    @patch("staarb.cli.backtest.OrderExecutor", autospec=True)
    @patch("staarb.cli.backtest.setup_backtest_subscribers", autospec=True)
    @patch("staarb.cli.backtest.EventBus.publish", new_callable=AsyncMock)
    async def test_run_loop_with_save(
        self, mock_eventbus_publish, mock_setup_subscribers, mock_order_executor_class, mock_trading_storage_class,
        common_loop_params, mock_client
    ):
        mock_storage_instance = AsyncMock()
        mock_trading_storage_class.return_value = mock_storage_instance

        await _run_backtest_loop(**common_loop_params, save=True)

        mock_trading_storage_class.assert_called_once_with(common_loop_params["storage_url"])
        mock_storage_instance.save_session.assert_called_once()
        args, _ = mock_storage_instance.save_session.call_args
        assert isinstance(args[0], SessionEvent)
        assert args[0].session_type == SessionType.BACKTEST
        assert args[0].start_time == common_loop_params["start_date"]
        assert args[0].end_time == common_loop_params["end_date"]

        mock_order_executor_class.assert_called_once_with(client=mock_client)
        mock_setup_subscribers.assert_called_once_with(
            common_loop_params["strategy"],
            common_loop_params["portfolio"],
            mock_order_executor_class.return_value, # instance of OrderExecutor
            mock_storage_instance,
        )

        expected_cur_pt = int(len(mock_client.ohlcv_data["BTCUSDT"]) * common_loop_params["train_val_split"])
        mock_client.set_current_pointer.assert_called_once_with(expected_cur_pt)

        assert mock_eventbus_publish.call_count == 2 # Based on get_mock_data returning 2 items
        for call_arg in mock_eventbus_publish.call_args_list:
            args, kwargs = call_arg
            assert args[0] == MarketDataEvent # Class
            assert isinstance(kwargs['data'], MarketDataEvent) # Instance

    @patch("staarb.cli.backtest.TradingStorage", autospec=True)
    @patch("staarb.cli.backtest.OrderExecutor", autospec=True)
    @patch("staarb.cli.backtest.setup_backtest_subscribers", autospec=True)
    @patch("staarb.cli.backtest.EventBus.publish", new_callable=AsyncMock)
    async def test_run_loop_without_save(
        self, mock_eventbus_publish, mock_setup_subscribers, mock_order_executor_class, mock_trading_storage_class,
        common_loop_params, mock_client
    ):
        await _run_backtest_loop(**common_loop_params, save=False)

        mock_trading_storage_class.assert_not_called()

        mock_order_executor_class.assert_called_once_with(client=mock_client)
        mock_setup_subscribers.assert_called_once_with(
            common_loop_params["strategy"],
            common_loop_params["portfolio"],
            mock_order_executor_class.return_value,
            None,  # Storage should be None
        )

        expected_cur_pt = int(len(mock_client.ohlcv_data["BTCUSDT"]) * common_loop_params["train_val_split"])
        mock_client.set_current_pointer.assert_called_once_with(expected_cur_pt)

        assert mock_eventbus_publish.call_count == 2


class TestBacktestCLI:
    """Test backtest CLI command."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    @patch("staarb.cli.backtest._setup_backtest_environment")
    @patch("staarb.cli.backtest._initialize_backtest_components", new_callable=AsyncMock)
    @patch("staarb.cli.backtest._run_backtest_loop", new_callable=AsyncMock)
    def test_backtest_orchestration(
        self, mock_run_loop, mock_init_components, mock_setup_env, runner
    ):
        """Test that the main backtest command correctly orchestrates helper calls."""
        mock_setup_env.return_value = ("mock_api_key", "mock_api_secret")

        mock_client_instance = AsyncMock(spec=MockClient)
        mock_client_instance.close_connection = AsyncMock() # Important for the finally block

        mock_portfolio_instance = MagicMock(spec=Portfolio)
        mock_strategy_instance = MagicMock(spec=StatisticalArbitrage)

        mock_init_components.return_value = (
            mock_client_instance,
            mock_portfolio_instance,
            mock_strategy_instance,
            12345, # mock start_time_ms
            67890  # mock end_time_ms
        )

        result = runner.invoke(
            backtest,
            [
                "BTCUSDT", "ETHUSDT",
                "2024-01-01", "2024-01-02",
                "--interval", "1h",
                "--train-val-split", "0.75",
                "--entry-threshold", "1.5",
                "--exit-threshold", "0.25",
                "--env-file", "test.env",
                "--api-key", "cmd_key", # Test pass-through of these
                "--api-secret", "cmd_secret",
                "--no-save",
                "--storage-url", "sqlite:///custom.db"
            ]
        )

        assert result.exit_code == 0, result.output
        assert "Backtest completed successfully" in result.output

        mock_setup_env.assert_called_once_with("test.env", "cmd_key", "cmd_secret")

        mock_init_components.assert_called_once()
        args, kwargs = mock_init_components.call_args
        assert kwargs['symbols'] == ["BTCUSDT", "ETHUSDT"]
        assert kwargs['start_date'] == datetime(2024, 1, 1)
        assert kwargs['end_date'] == datetime(2024, 1, 2)
        assert kwargs['interval'] == "1h"
        assert kwargs['train_val_split'] == 0.75
        assert kwargs['entry_threshold'] == 1.5
        assert kwargs['exit_threshold'] == 0.25
        assert kwargs['api_key'] == "mock_api_key" # from mock_setup_env
        assert kwargs['api_secret'] == "mock_api_secret" # from mock_setup_env

        mock_run_loop.assert_called_once()
        args_run, kwargs_run = mock_run_loop.call_args
        assert kwargs_run['client'] == mock_client_instance
        assert kwargs_run['strategy'] == mock_strategy_instance
        assert kwargs_run['portfolio'] == mock_portfolio_instance
        assert kwargs_run['storage_url'] == "sqlite:///custom.db"
        assert kwargs_run['save'] is False
        assert kwargs_run['start_date'] == datetime(2024,1,1)
        assert kwargs_run['end_date'] == datetime(2024,1,2)
        assert kwargs_run['symbols'] == ["BTCUSDT", "ETHUSDT"]
        assert kwargs_run['train_val_split'] == 0.75

        mock_client_instance.close_connection.assert_called_once()


    @patch("staarb.cli.backtest._setup_backtest_environment")
    @patch("staarb.cli.backtest._initialize_backtest_components", new_callable=AsyncMock)
    def test_backtest_exception_after_init(
        self, mock_init_components, mock_setup_env, runner
    ):
        """Test exception handling if _run_backtest_loop (or init itself) fails."""
        mock_setup_env.return_value = ("mock_api_key", "mock_api_secret")

        mock_client_instance = AsyncMock(spec=MockClient)
        mock_client_instance.close_connection = AsyncMock()

        # Simulate _initialize_backtest_components succeeding but _run_backtest_loop (or later) failing
        mock_init_components.return_value = (
            mock_client_instance, MagicMock(), MagicMock(), 123, 456
        )
        # Make _run_backtest_loop (implicitly called after init) raise an error
        with patch("staarb.cli.backtest._run_backtest_loop", new_callable=AsyncMock, side_effect=ValueError("Loop error")):
            result = runner.invoke(
                backtest,
                ["BTCUSDT", "2024-01-01", "2024-01-02", "--no-save"]
            )

        assert result.exit_code == 1
        assert "An error occurred during backtest: Loop error" in result.output
        mock_client_instance.close_connection.assert_called_once() # Crucial: finally block test

    # Keep existing tests for direct CLI invocation if they cover other aspects
    # For example, tests that don't deeply mock the helpers but check Click behavior
    # The following are adapted slightly to use the new structure where appropriate

    def test_backtest_with_api_credentials_via_env(self, runner): # Renamed to be more specific
        """Test backtest with API credentials from OS ENV."""
        with (
            patch.dict("os.environ", {"BINANCE_API_KEY": "test_key_env", "BINANCE_API_SECRET": "test_secret_env"}),
            patch("staarb.cli.backtest._initialize_backtest_components", new_callable=AsyncMock) as mock_init_components,
            patch("staarb.cli.backtest._run_backtest_loop", new_callable=AsyncMock) as mock_run_loop,
        ):
            mock_client = AsyncMock(spec=MockClient); mock_client.close_connection = AsyncMock()
            mock_init_components.return_value = (mock_client, MagicMock(), MagicMock(), 1, 2)

            result = runner.invoke(
                backtest, ["BTCUSDT", "2024-01-01", "2024-01-02", "--no-save"]
            )
            assert result.exit_code == 0

            # Check that _initialize_backtest_components was called with keys from env
            args, kwargs = mock_init_components.call_args
            assert kwargs['api_key'] == "test_key_env"
            assert kwargs['api_secret'] == "test_secret_env"

    def test_backtest_env_file_loading_integration(self, runner): # Renamed for clarity
        """Test backtest with env file loading (integration style)."""
        # This test is more of an integration test for _setup_backtest_environment
        # when called from the main CLI command.
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_env_file:
            tmp_env_file.write("BINANCE_API_KEY=key_from_tmp_file\n")
            tmp_env_file.write("BINANCE_API_SECRET=secret_from_tmp_file\n")
            env_file_path = tmp_env_file.name

        try:
            with (
                patch("staarb.cli.backtest._initialize_backtest_components", new_callable=AsyncMock) as mock_init_components,
                patch("staarb.cli.backtest._run_backtest_loop", new_callable=AsyncMock) as mock_run_loop,
                 # We let _setup_backtest_environment run mostly unmocked for this test,
                 # only mocking load_dotenv to prevent it from actually loading a default .env
                patch("dotenv.load_dotenv") as mock_actual_load_dotenv
            ):
                mock_client = AsyncMock(spec=MockClient); mock_client.close_connection = AsyncMock()
                mock_init_components.return_value = (mock_client, MagicMock(), MagicMock(), 1,2)

                result = runner.invoke(
                    backtest,
                    ["BTCUSDT", "2024-01-01", "2024-01-02", "--env-file", env_file_path, "--no-save"]
                )
                assert result.exit_code == 0

                # Verify load_dotenv was called for the specified file
                mock_actual_load_dotenv.assert_any_call(dotenv_path=env_file_path)

                args, kwargs = mock_init_components.call_args
                assert kwargs['api_key'] == "key_from_tmp_file"
                assert kwargs['api_secret'] == "secret_from_tmp_file"
        finally:
            os.remove(env_file_path)

    # Example of how an existing test might be simplified or focused
    @patch("staarb.cli.backtest._setup_backtest_environment")
    @patch("staarb.cli.backtest._initialize_backtest_components", new_callable=AsyncMock)
    @patch("staarb.cli.backtest._run_backtest_loop", new_callable=AsyncMock)
    def test_backtest_custom_params_passed_to_init(
        self, mock_run_loop, mock_init_components, mock_setup_env, runner
    ):
        """Test that custom CLI parameters are passed to _initialize_backtest_components."""
        mock_setup_env.return_value = ("key", "secret")
        mock_client = AsyncMock(spec=MockClient); mock_client.close_connection = AsyncMock()
        mock_init_components.return_value = (mock_client, MagicMock(), MagicMock(), 1, 2)

        runner.invoke(
            backtest,
            [
                "SYM", "2024-01-01", "2024-01-31",
                "--interval", "4h",
                "--train-val-split", "0.7",
                "--entry-threshold", "2.0",
                "--exit-threshold", "0.5",
                "--no-save",
            ],
        )

        args, kwargs = mock_init_components.call_args
        assert kwargs['interval'] == "4h"
        assert kwargs['train_val_split'] == 0.7
        assert kwargs['entry_threshold'] == 2.0
        assert kwargs['exit_threshold'] == 0.5

        # _run_backtest_loop should also get these if needed (e.g. train_val_split for cur_pt)
        args_run, kwargs_run = mock_run_loop.call_args
        assert kwargs_run['train_val_split'] == 0.7


    @patch("staarb.cli.backtest._setup_backtest_environment")
    @patch("staarb.cli.backtest._initialize_backtest_components", new_callable=AsyncMock)
    @patch("staarb.cli.backtest._run_backtest_loop", new_callable=AsyncMock)
    def test_backtest_save_options_passed_to_run_loop(
        self, mock_run_loop, mock_init_components, mock_setup_env, runner
    ):
        """Test that save options are passed to _run_backtest_loop."""
        mock_setup_env.return_value = ("key", "secret")
        mock_client = AsyncMock(spec=MockClient); mock_client.close_connection = AsyncMock()
        mock_init_components.return_value = (mock_client, MagicMock(), MagicMock(), 1, 2)

        runner.invoke(
            backtest,
            [
                "SYM", "2024-01-01", "2024-01-02",
                "--save", "--storage-url", "sqlite:///test.db",
            ],
        )

        args, kwargs = mock_run_loop.call_args
        assert kwargs['save'] is True
        assert kwargs['storage_url'] == "sqlite:///test.db"

        # Test --no-save
        runner.invoke(
            backtest,
            ["SYM", "2024-01-01", "2024-01-02", "--no-save"],
        )
        args, kwargs = mock_run_loop.call_args # from the latest call
        assert kwargs['save'] is False
