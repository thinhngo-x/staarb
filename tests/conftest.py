"""Shared pytest fixtures and configuration."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from staarb.core.types import Symbol


@pytest.fixture
def sample_symbol():
    """Create a sample Symbol for testing."""
    return Symbol(
        symbol="BTCUSDT",
        baseAsset="BTC",
        quoteAsset="USDT",
        baseAssetPrecision=8,
        quoteAssetPrecision=8,
        filters=[
            {
                "filterType": "LOT_SIZE",
                "minQty": "0.00001000",
                "maxQty": "9000.00000000",
                "stepSize": "0.00001000",
            }
        ],
    )


@pytest.fixture
def sample_symbols():
    """Create multiple sample symbols."""
    return [
        Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        ),
        Symbol(
            symbol="ETHUSDT",
            baseAsset="ETH",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        ),
    ]


@pytest.fixture
def sample_market_data():
    """Create sample market data for testing."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    return {
        "BTCUSDT": pd.DataFrame({"close": [50000 + i * 100 for i in range(10)]}, index=dates),
        "ETHUSDT": pd.DataFrame({"close": [3000 + i * 50 for i in range(10)]}, index=dates),
    }


@pytest.fixture
def sample_datetime():
    """Create a sample datetime for testing."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_client():
    """Create a mock client for testing."""
    client = MagicMock()
    client.close_connection = MagicMock()
    return client


@pytest.fixture
async def async_mock_client():
    """Create an async mock client for testing."""
    from staarb.clients.mock import MockClient
    from staarb.core.types import DataRequest

    # Create minimal test data
    sample_symbols = [
        Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        ),
        Symbol(
            symbol="ETHUSDT",
            baseAsset="ETH",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        ),
    ]

    sample_data_request = DataRequest(
        start_date=datetime(2024, 1, 1, tzinfo=UTC), end_date=datetime(2024, 1, 10, tzinfo=UTC), interval="1d"
    )

    sample_balance = {"USDT": {"free": 1000.0, "locked": 0.0, "borrowed": 0.0, "interest": 0.0}}

    test_api_key = "test_key"
    test_api_secret = "test_secret"  # noqa: S105

    client = await MockClient.create(
        symbols=sample_symbols,
        dreq=sample_data_request,
        balance=sample_balance,
        api_key=test_api_key,
        api_secret=test_api_secret,
    )

    yield client

    await client.close_connection()

    # Remove the deprecated event_loop fixture
    """Create an instance of the default event loop for the test session."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
