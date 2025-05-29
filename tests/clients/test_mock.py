from datetime import datetime
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from staarb.clients.mock import MockClient
from staarb.core.types import DataRequest, LookbackRequest


class TestMockClient:
    """Test MockClient functionality."""

    @pytest.fixture
    def sample_data_request(self):
        """Create a sample DataRequest."""
        return DataRequest(
            interval="1d",
            start=1640995200000,  # 2022-01-01
            end=1641081600000,  # 2022-01-02
            columns=["close"],
        )

    @pytest.fixture
    def sample_balance(self):
        """Create sample balance."""
        return {"USDC": 1000.0, "BTC": 0.1}

    @pytest.fixture
    def mock_client_sync(self, sample_data_request, sample_balance):
        """Create a MockClient instance for synchronous testing."""
        import asyncio

        symbols = ["BTCUSDT", "ETHUSDT"]

        # Mock the MarketDataFetcher.fetch_multiple_klines
        mock_data = {
            "BTCUSDT": pd.DataFrame(
                {"close": [50000.0, 51000.0, 52000.0]},
                index=pd.to_datetime(["2022-01-01", "2022-01-02", "2022-01-03"]),
            ),
            "ETHUSDT": pd.DataFrame(
                {"close": [3000.0, 3100.0, 3200.0]},
                index=pd.to_datetime(["2022-01-01", "2022-01-02", "2022-01-03"]),
            ),
        }

        with patch(
            "staarb.clients.mock.MarketDataFetcher.fetch_multiple_klines", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_data

            test_api_key = "test_key"
            test_api_secret = "test_secret"  # noqa: S105

            # Create client synchronously for sync tests
            client = asyncio.run(
                MockClient.create(
                    symbols=symbols,
                    dreq=sample_data_request,
                    balance=sample_balance,
                    api_key=test_api_key,
                    api_secret=test_api_secret,
                )
            )

            yield client
            asyncio.run(client.close_connection())

    @pytest.fixture
    async def mock_client_async(self, sample_data_request, sample_balance):
        """Create a MockClient instance for async testing."""
        symbols = ["BTCUSDT", "ETHUSDT"]

        # Mock the MarketDataFetcher.fetch_multiple_klines
        mock_data = {
            "BTCUSDT": pd.DataFrame(
                {"close": [50000.0, 51000.0, 52000.0]},
                index=pd.to_datetime(["2022-01-01", "2022-01-02", "2022-01-03"]),
            ),
            "ETHUSDT": pd.DataFrame(
                {"close": [3000.0, 3100.0, 3200.0]},
                index=pd.to_datetime(["2022-01-01", "2022-01-02", "2022-01-03"]),
            ),
        }

        with patch(
            "staarb.clients.mock.MarketDataFetcher.fetch_multiple_klines", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_data

            test_api_key = "test_key"
            test_api_secret = "test_secret"  # noqa: S105

            client = await MockClient.create(
                symbols=symbols,
                dreq=sample_data_request,
                balance=sample_balance,
                api_key=test_api_key,
                api_secret=test_api_secret,
            )

            yield client
            await client.close_connection()

    def test_gain_asset(self, mock_client_sync):
        """Test gaining assets in mock balance."""
        mock_client_sync.gain("USDC", 500.0)

        assert mock_client_sync._asset_balance["USDC"]["free"] == 1500.0
        assert mock_client_sync._asset_balance["USDC"]["borrowed"] == 0.0

    def test_gain_asset_with_borrowed_amount(self, mock_client_sync):
        """Test gaining assets when there's borrowed amount."""
        # First borrow some amount
        mock_client_sync._asset_balance["USDC"] = {
            "free": 0.0,
            "locked": 0.0,
            "borrowed": 200.0,
            "interest": 0.0,
        }

        # Gain amount that partially covers borrowed amount
        mock_client_sync.gain("USDC", 100.0)

        assert mock_client_sync._asset_balance["USDC"]["free"] == 0.0
        assert mock_client_sync._asset_balance["USDC"]["borrowed"] == 100.0

        # Gain amount that fully covers borrowed amount with excess
        mock_client_sync.gain("USDC", 300.0)

        assert mock_client_sync._asset_balance["USDC"]["free"] == 200.0
        assert mock_client_sync._asset_balance["USDC"]["borrowed"] == 0.0

    def test_pay_asset(self, mock_client_sync):
        """Test paying assets from mock balance."""
        mock_client_sync.pay("USDC", 200.0)

        assert mock_client_sync._asset_balance["USDC"]["free"] == 800.0
        assert mock_client_sync._asset_balance["USDC"]["borrowed"] == 0.0

    def test_pay_asset_insufficient_balance(self, mock_client_sync):
        """Test paying more than available balance triggers borrowing."""
        mock_client_sync.pay("USDC", 1200.0)

        assert mock_client_sync._asset_balance["USDC"]["free"] == 0.0
        assert mock_client_sync._asset_balance["USDC"]["borrowed"] == 200.0

    def test_pay_new_asset(self, mock_client_sync):
        """Test paying an asset not in balance."""
        mock_client_sync.pay("ETH", 0.5)

        assert "ETH" in mock_client_sync._asset_balance
        assert mock_client_sync._asset_balance["ETH"]["free"] == 0.0
        assert mock_client_sync._asset_balance["ETH"]["borrowed"] == 0.5

    def test_set_and_get_current_pointer(self, mock_client_sync):
        """Test setting and getting current pointer."""
        mock_client_sync.set_current_pointer(5)
        assert mock_client_sync._current_pt == 5

    def test_get_current_time(self, mock_client_sync):
        """Test getting current mock time."""
        mock_client_sync.set_current_pointer(1)
        current_time = mock_client_sync.get_current_time()

        assert isinstance(current_time, datetime)

    def test_get_mock_data_insufficient_pointer(self, mock_client_sync):
        """Test get_mock_data with insufficient current pointer."""
        lookback_req = LookbackRequest(interval="1d", limit=10)
        mock_client_sync.set_current_pointer(5)  # Less than limit

        with pytest.raises(ValueError, match="Current pointer .* is less than the limit"):
            list(mock_client_sync.get_mock_data(lookback_req))

    def test_get_mock_data_iteration(self, mock_client_sync):
        """Test iterating through mock data."""
        lookback_req = LookbackRequest(interval="1d", limit=2)
        mock_client_sync.set_current_pointer(2)

        data_generator = mock_client_sync.get_mock_data(lookback_req)
        first_batch = next(data_generator)

        assert "BTCUSDT" in first_batch
        assert "ETHUSDT" in first_batch
        assert len(first_batch["BTCUSDT"]) == 2

    @pytest.mark.asyncio
    async def test_get_margin_account(self, mock_client_async):
        """Test getting margin account information."""
        async for client in mock_client_async:
            account_info = await client.get_margin_account()

            assert "userAssets" in account_info
            user_assets = account_info["userAssets"]

            # Should have USDC and BTC from initial balance
            asset_names = [asset["asset"] for asset in user_assets]
            assert "USDC" in asset_names
            assert "BTC" in asset_names
            break

    @pytest.mark.asyncio
    async def test_create_margin_order_buy(self, mock_client_async):
        """Test creating a buy margin order."""
        with patch("staarb.data.exchange_info_fetcher.BinanceExchangeInfo.get_symbol_info") as mock_symbol:
            # Mock symbol info
            mock_symbol_obj = type("Symbol", (), {"base_asset": "BTC", "quote_asset": "USDT"})()
            mock_symbol.return_value = mock_symbol_obj

            async for client in mock_client_async:
                client.set_current_pointer(1)

                result = await client.create_margin_order(symbol="BTCUSDT", quantity=0.1, side="BUY")

                assert result["symbol"] == "BTCUSDT"
                assert result["status"] == "FILLED"
                assert result["executedQty"] == 0.1
                assert len(result["fills"]) == 1
                break

    @pytest.mark.asyncio
    async def test_create_margin_order_sell(self, mock_client_async):
        """Test creating a sell margin order."""
        with patch("staarb.data.exchange_info_fetcher.BinanceExchangeInfo.get_symbol_info") as mock_symbol:
            # Mock symbol info
            mock_symbol_obj = type("Symbol", (), {"base_asset": "BTC", "quote_asset": "USDT"})()
            mock_symbol.return_value = mock_symbol_obj

            async for client in mock_client_async:
                client.set_current_pointer(1)

                result = await client.create_margin_order(symbol="BTCUSDT", quantity=0.05, side="SELL")

                assert result["symbol"] == "BTCUSDT"
                assert result["status"] == "FILLED"
                assert result["executedQty"] == 0.05
                break

    @pytest.mark.asyncio
    async def test_create_margin_order_unknown_symbol(self, mock_client_async):
        """Test creating order for unknown symbol raises error."""
        async for client in mock_client_async:
            with pytest.raises(ValueError, match="Symbol .* not found in mock data"):
                await client.create_margin_order(symbol="UNKNOWN", quantity=0.1, side="BUY")
            break
