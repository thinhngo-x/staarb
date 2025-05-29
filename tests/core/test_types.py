import pytest

from staarb.core.enums import OrderSide
from staarb.core.types import (
    DataRequest,
    Fill,
    Filters,
    LookbackRequest,
    LotSizeFilter,
    Order,
    Symbol,
    Transaction,
)


class TestLotSizeFilter:
    """Test LotSizeFilter dataclass."""

    def test_lot_size_filter_creation(self):
        """Test creating LotSizeFilter."""
        filter_obj = LotSizeFilter(min_qty="0.001", max_qty="1000", step_size="0.001")
        assert filter_obj.min_qty == "0.001"
        assert filter_obj.max_qty == "1000"
        assert filter_obj.step_size == "0.001"


class TestFilters:
    """Test Filters class with initialization from filter configs."""

    def test_filters_initialization(self):
        """Test Filters initialization with filter configs."""
        filter_configs = [
            {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "1000", "stepSize": "0.001"},
            {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "10000", "tickSize": "0.01"},
            {"filterType": "NOTIONAL", "minNotional": "10", "maxNotional": "50000"},
        ]

        filters = Filters(*filter_configs)

        assert filters.lot_size.min_qty == "0.001"
        assert filters.price.tick_size == "0.01"
        assert filters.notional.min_notional == "10"


class TestSymbol:
    """Test Symbol class."""

    def test_symbol_creation_from_kwargs(self):
        """Test creating Symbol from API response kwargs."""
        symbol_data = {
            "symbol": "BTCUSDT",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "baseAssetPrecision": 8,
            "quoteAssetPrecision": 8,
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00001000",
                    "maxQty": "9000.00000000",
                    "stepSize": "0.00001000",
                }
            ],
        }

        symbol = Symbol(**symbol_data)
        assert symbol.name == "BTCUSDT"
        assert symbol.base_asset == "BTC"
        assert symbol.quote_asset == "USDT"
        assert str(symbol) == "BTCUSDT"

    def test_symbol_equality(self):
        """Test Symbol equality comparison."""
        symbol1 = Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )
        symbol2 = Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )
        symbol3 = Symbol(
            symbol="ETHUSDT",
            baseAsset="ETH",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )

        assert symbol1 == symbol2
        assert symbol1 != symbol3

    def test_symbol_equality_with_non_symbol(self):
        """Test Symbol equality with non-Symbol object raises TypeError."""
        symbol = Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )

        with pytest.raises(TypeError):
            _ = symbol == "BTCUSDT"

    def test_symbol_hash(self):
        """Test Symbol can be used as dict key."""
        symbol1 = Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )
        symbol2 = Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )

        symbol_dict = {symbol1: "value1"}
        assert symbol_dict[symbol2] == "value1"  # Should find same symbol


class TestDataRequest:
    """Test DataRequest dataclass."""

    def test_data_request_with_default_columns(self):
        """Test DataRequest with default columns."""
        request = DataRequest(interval="1d", start=1640995200000, end=1641081600000)
        assert request.columns == ["close"]

    def test_data_request_with_custom_columns(self):
        """Test DataRequest with custom columns."""
        request = DataRequest(
            interval="1h", start=1640995200000, end=1641081600000, columns=["open", "high", "low", "close"]
        )
        assert request.columns == ["open", "high", "low", "close"]


class TestLookbackRequest:
    """Test LookbackRequest dataclass."""

    def test_lookback_request_defaults(self):
        """Test LookbackRequest with defaults."""
        request = LookbackRequest(interval="1d", limit=100)
        assert request.columns == ["close"]

    def test_lookback_request_custom_columns(self):
        """Test LookbackRequest with custom columns."""
        request = LookbackRequest(interval="1h", limit=50, columns=["open", "close", "volume"])
        assert request.columns == ["open", "close", "volume"]


class TestFill:
    """Test Fill class."""

    @pytest.fixture
    def btc_symbol(self):
        """Create a BTC symbol for testing."""
        return Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )

    def test_fill_creation_with_quote_commission(self, btc_symbol):
        """Test Fill creation when commission is in quote asset."""
        fill = Fill(symbol=btc_symbol, price=50000.0, quantity=0.1, commission=5.0, commission_asset="USDT")

        assert fill.symbol == btc_symbol
        assert fill.price == 50000.0
        assert fill.quantity == 0.1
        assert fill.base_quantity == 0.1  # No commission deduction from base
        assert fill.quote_quantity == 4995.0  # 50000 * 0.1 - 5 commission

    def test_fill_creation_with_base_commission(self, btc_symbol):
        """Test Fill creation when commission is in base asset."""
        fill = Fill(symbol=btc_symbol, price=50000.0, quantity=0.1, commission=0.001, commission_asset="BTC")

        assert fill.base_quantity == 0.099  # 0.1 - 0.001 commission
        assert fill.quote_quantity == 5000.0  # No commission deduction from quote


class TestOrder:
    """Test Order dataclass."""

    @pytest.fixture
    def btc_symbol(self):
        """Create a BTC symbol for testing."""
        return Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )

    def test_order_creation_market_buy(self, btc_symbol):
        """Test creating a market buy order."""
        order = Order(symbol=btc_symbol, quantity=0.1, side=OrderSide.BUY)

        assert order.symbol == btc_symbol
        assert order.quantity == 0.1
        assert order.side == OrderSide.BUY
        assert order.type == "MARKET"
        assert order.price is None

    def test_order_creation_limit_sell(self, btc_symbol):
        """Test creating a limit sell order."""
        order = Order(symbol=btc_symbol, quantity=0.05, side=OrderSide.SELL, price=51000.0, type="LIMIT")

        assert order.price == 51000.0
        assert order.type == "LIMIT"


class TestTransaction:
    """Test Transaction class."""

    @pytest.fixture
    def btc_symbol(self):
        """Create a BTC symbol for testing."""
        return Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )

    @pytest.fixture
    def sample_order(self, btc_symbol):
        """Create a sample order."""
        return Order(symbol=btc_symbol, quantity=0.1, side=OrderSide.BUY)

    @pytest.fixture
    def sample_fill(self, btc_symbol):
        """Create a sample fill."""
        return Fill(symbol=btc_symbol, price=50000.0, quantity=0.1, commission=0.001, commission_asset="BTC")

    def test_transaction_creation(self, sample_order, sample_fill):
        """Test Transaction creation."""
        transaction = Transaction(order=sample_order, fills=[sample_fill], transact_time=1640995200000)

        assert transaction.order == sample_order
        assert len(transaction.fills) == 1
        assert transaction.transact_time == 1640995200000

    def test_transaction_empty_fills_raises_error(self, sample_order):
        """Test Transaction with empty fills raises ValueError."""
        with pytest.raises(ValueError, match="Transaction must have at least one fill"):
            Transaction(order=sample_order, fills=[], transact_time=1640995200000)

    def test_transaction_non_list_fills_raises_error(self, sample_order, sample_fill):
        """Test Transaction with non-list fills raises TypeError."""
        with pytest.raises(TypeError, match="Transaction fills must be a list"):
            Transaction(
                order=sample_order,
                fills=sample_fill,  # Single fill instead of list
                transact_time=1640995200000,
            )

    def test_transaction_symbol_mismatch_raises_error(self, btc_symbol):
        """Test Transaction with mismatched symbols raises ValueError."""
        eth_symbol = Symbol(
            symbol="ETHUSDT",
            baseAsset="ETH",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )

        order = Order(symbol=btc_symbol, quantity=0.1, side=OrderSide.BUY)
        fill = Fill(symbol=eth_symbol, price=3000.0, quantity=1.0, commission=0.1, commission_asset="ETH")

        with pytest.raises(ValueError, match="Order symbol .* does not match fill symbol"):
            Transaction(order=order, fills=[fill], transact_time=1640995200000)

    def test_transaction_avg_fill_price(self, sample_order, btc_symbol):
        """Test Transaction average fill price calculation."""
        fill1 = Fill(
            symbol=btc_symbol, price=50000.0, quantity=0.05, commission=0.0005, commission_asset="BTC"
        )
        fill2 = Fill(
            symbol=btc_symbol, price=50100.0, quantity=0.05, commission=0.0005, commission_asset="BTC"
        )

        transaction = Transaction(order=sample_order, fills=[fill1, fill2], transact_time=1640995200000)

        avg_price = transaction.avg_fill_price()
        expected_avg = (2500.0 + 2505.0) / (0.0495 + 0.0495)  # quote_qty / base_qty
        assert abs(avg_price - expected_avg) < 0.01
