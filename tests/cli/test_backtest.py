import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from staarb.cli.backtest import backtest


class TestBacktestCLI:
    """Test backtest CLI command."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_backtest_with_api_credentials(self, runner):
        """Test backtest with provided API credentials."""
        with (
            patch.dict("os.environ", {"BINANCE_API_KEY": "test_key", "BINANCE_API_SECRET": "test_secret"}),
            patch("staarb.cli.backtest.MockClient.create", new_callable=AsyncMock) as mock_create,
            patch("staarb.cli.backtest.BinanceExchangeInfo.fetch_exchange_info", new_callable=AsyncMock),
            patch("staarb.cli.backtest.MarketDataFetcher.fetch_multiple_klines", new_callable=AsyncMock),
            patch("staarb.cli.backtest.Portfolio") as mock_portfolio_class,
            patch("staarb.cli.backtest.StatisticalArbitrage") as mock_strategy_class,
            patch("staarb.cli.backtest.OrderExecutor"),
        ):
            # Setup mocks
            mock_client = MagicMock()
            mock_client.close_connection = AsyncMock()
            mock_client.get_mock_data.return_value = iter([])
            mock_create.return_value = mock_client

            mock_portfolio = MagicMock()
            mock_portfolio_class.return_value = mock_portfolio

            mock_strategy = MagicMock()
            mock_strategy.get_lookback_request.return_value = MagicMock()
            mock_strategy_class.return_value = mock_strategy

            result = runner.invoke(
                backtest,
                [
                    "BTCUSDT",
                    "ETHUSDT",
                    "2024-01-01",
                    "2024-01-02",
                    "--no-save",
                ],
            )

            assert result.exit_code == 0
            assert "Running backtest for symbols: BTCUSDT, ETHUSDT" in result.output
            assert "Backtest completed successfully" in result.output

    def test_backtest_with_custom_parameters(self, runner):
        """Test backtest with custom parameters."""
        with (
            patch.dict("os.environ", {"BINANCE_API_KEY": "test_key", "BINANCE_API_SECRET": "test_secret"}),
            patch("staarb.cli.backtest.MockClient.create", new_callable=AsyncMock) as mock_create,
            patch("staarb.cli.backtest.BinanceExchangeInfo.fetch_exchange_info", new_callable=AsyncMock),
            patch("staarb.cli.backtest.MarketDataFetcher.fetch_multiple_klines", new_callable=AsyncMock),
            patch("staarb.cli.backtest.Portfolio") as mock_portfolio_class,
            patch("staarb.cli.backtest.StatisticalArbitrage") as mock_strategy_class,
            patch("staarb.cli.backtest.OrderExecutor"),
        ):
            # Setup mocks
            mock_client = MagicMock()
            mock_client.close_connection = AsyncMock()
            mock_client.get_mock_data.return_value = iter([])
            mock_create.return_value = mock_client

            mock_portfolio = MagicMock()
            mock_portfolio_class.return_value = mock_portfolio

            mock_strategy = MagicMock()
            mock_strategy.get_lookback_request.return_value = MagicMock()
            mock_strategy_class.return_value = mock_strategy

            result = runner.invoke(
                backtest,
                [
                    "BTCUSDT",
                    "2024-01-01",
                    "2024-01-31",
                    "--interval",
                    "4h",
                    "--train-val-split",
                    "0.7",
                    "--entry-threshold",
                    "2.0",
                    "--exit-threshold",
                    "0.5",
                    "--no-save",
                ],
            )

            assert result.exit_code == 0
            # Verify strategy was called with custom parameters
            mock_strategy_class.assert_called_once_with("4h", entry_threshold=2.0, exit_threshold=0.5)

    def test_backtest_with_save_enabled(self, runner):
        """Test backtest with saving enabled."""
        with (
            patch.dict("os.environ", {"BINANCE_API_KEY": "test_key", "BINANCE_API_SECRET": "test_secret"}),
            patch("staarb.cli.backtest.MockClient.create", new_callable=AsyncMock) as mock_create,
            patch("staarb.cli.backtest.BinanceExchangeInfo.fetch_exchange_info", new_callable=AsyncMock),
            patch("staarb.cli.backtest.MarketDataFetcher.fetch_multiple_klines", new_callable=AsyncMock),
            patch("staarb.cli.backtest.Portfolio") as mock_portfolio_class,
            patch("staarb.cli.backtest.StatisticalArbitrage") as mock_strategy_class,
            patch("staarb.cli.backtest.OrderExecutor"),
            patch("staarb.cli.backtest.TradingStorage") as mock_storage_class,
        ):
            # Setup mocks
            mock_client = MagicMock()
            mock_client.close_connection = AsyncMock()
            mock_client.get_mock_data.return_value = iter([])
            mock_create.return_value = mock_client

            mock_portfolio = MagicMock()
            mock_portfolio_class.return_value = mock_portfolio

            mock_strategy = MagicMock()
            mock_strategy.get_lookback_request.return_value = MagicMock()
            mock_strategy_class.return_value = mock_strategy

            mock_storage = MagicMock()
            mock_storage.save_session = AsyncMock()
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(
                backtest,
                [
                    "BTCUSDT",
                    "2024-01-01",
                    "2024-01-02",
                    "--save",
                    "--storage-url",
                    "sqlite:///test.db",
                ],
            )

            assert result.exit_code == 0
            assert "Backtest completed successfully" in result.output
            mock_storage.save_session.assert_called_once()

    def test_backtest_exception_handling(self, runner):
        """Test backtest exception handling."""
        with (
            patch.dict("os.environ", {"BINANCE_API_KEY": "test_key", "BINANCE_API_SECRET": "test_secret"}),
            patch("staarb.cli.backtest.MockClient.create", new_callable=AsyncMock) as mock_create,
        ):
            # Make MockClient.create raise an exception
            mock_create.side_effect = ValueError("Test error")

            result = runner.invoke(backtest, ["BTCUSDT", "2024-01-01", "2024-01-02", "--no-save"])

            assert result.exit_code == 1
            assert "An error occurred during backtest: Test error" in result.output

    def test_backtest_save_error_handling(self, runner):
        """Test backtest save error handling."""
        with (
            patch.dict("os.environ", {"BINANCE_API_KEY": "test_key", "BINANCE_API_SECRET": "test_secret"}),
            patch("staarb.cli.backtest.MockClient.create", new_callable=AsyncMock) as mock_create,
            patch("staarb.cli.backtest.BinanceExchangeInfo.fetch_exchange_info", new_callable=AsyncMock),
            patch("staarb.cli.backtest.MarketDataFetcher.fetch_multiple_klines", new_callable=AsyncMock),
            patch("staarb.cli.backtest.Portfolio") as mock_portfolio_class,
            patch("staarb.cli.backtest.StatisticalArbitrage") as mock_strategy_class,
            patch("staarb.cli.backtest.OrderExecutor"),
            patch("staarb.cli.backtest.TradingStorage") as mock_storage_class,
        ):
            # Setup mocks
            mock_client = MagicMock()
            mock_client.close_connection = AsyncMock()
            mock_client.get_mock_data.return_value = iter([])
            mock_create.return_value = mock_client

            mock_portfolio = MagicMock()
            mock_portfolio_class.return_value = mock_portfolio

            mock_strategy = MagicMock()
            mock_strategy.get_lookback_request.return_value = MagicMock()
            mock_strategy_class.return_value = mock_strategy

            mock_storage = MagicMock()
            mock_storage.save_session = AsyncMock(side_effect=OSError("Connection failed"))
            mock_storage_class.return_value = mock_storage

            result = runner.invoke(
                backtest,
                [
                    "BTCUSDT",
                    "2024-01-01",
                    "2024-01-02",
                    "--save",
                    "--storage-url",
                    "sqlite:///test.db",
                ],
            )

            assert result.exit_code == 1
            assert "An error occurred during backtest:" in result.output

    def test_backtest_env_file_loading(self, runner):
        """Test backtest with env file loading."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as env_file:
            env_file.write("BINANCE_API_KEY=test_key_from_file\n")
            env_file.write("BINANCE_API_SECRET=test_secret_from_file\n")
            env_file.flush()

            with (
                patch("staarb.cli.backtest.MockClient.create", new_callable=AsyncMock) as mock_create,
                patch("staarb.cli.backtest.BinanceExchangeInfo.fetch_exchange_info", new_callable=AsyncMock),
                patch("staarb.cli.backtest.MarketDataFetcher.fetch_multiple_klines", new_callable=AsyncMock),
                patch("staarb.cli.backtest.Portfolio") as mock_portfolio_class,
                patch("staarb.cli.backtest.StatisticalArbitrage") as mock_strategy_class,
                patch("staarb.cli.backtest.OrderExecutor"),
            ):
                # Setup mocks
                mock_client = MagicMock()
                mock_client.close_connection = AsyncMock()
                mock_client.get_mock_data.return_value = iter([])
                mock_create.return_value = mock_client

                mock_portfolio = MagicMock()
                mock_portfolio_class.return_value = mock_portfolio

                mock_strategy = MagicMock()
                mock_strategy.get_lookback_request.return_value = MagicMock()
                mock_strategy_class.return_value = mock_strategy

                result = runner.invoke(
                    backtest,
                    [
                        "BTCUSDT",
                        "2024-01-01",
                        "2024-01-02",
                        "--env-file",
                        env_file.name,
                        "--no-save",
                    ],
                )

                assert result.exit_code == 0
                # Verify the mock was called (indicating credentials were loaded)
                mock_create.assert_called_once()
