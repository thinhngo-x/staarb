import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from staarb.core.bus.events import OrderCreatedEvent, TransactionClosedEvent
from staarb.core.enums import OrderSide, PositionDirection
from staarb.core.types import Order, Symbol, Transaction
from staarb.trader.order_executor import OrderExecutor


@pytest.fixture
def mock_client():
    """Create a mock Binance client."""
    return AsyncMock()


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
def sample_order(sample_symbol):
    """Create a sample Order for testing."""
    return Order(
        symbol=sample_symbol,
        quantity=1.0,
        side=OrderSide.BUY,
        price=50000.0,
        type="LIMIT",
        time_in_force="GTC",
    )


@pytest.fixture
def sample_market_order(sample_symbol):
    """Create a sample market Order for testing."""
    return Order(symbol=sample_symbol, quantity=1.0, side=OrderSide.SELL, type="MARKET")


@pytest.fixture
def sample_order_created_event(sample_order):
    """Create a sample OrderCreatedEvent for testing."""
    return OrderCreatedEvent(orders=[sample_order])


@pytest.fixture
def sample_multiple_orders_event(sample_symbol):
    """Create an OrderCreatedEvent with multiple orders."""
    orders = [
        Order(
            symbol=sample_symbol,
            quantity=1.0,
            side=OrderSide.BUY,
            price=50000.0,
        ),
        Order(
            symbol=sample_symbol,
            quantity=0.5,
            side=OrderSide.SELL,
            price=51000.0,
        ),
    ]
    return OrderCreatedEvent(orders=orders)


@pytest.fixture
def sample_binance_response():
    """Create a sample Binance API response."""
    return {
        "symbol": "BTCUSDT",
        "orderId": 123456,
        "transactTime": 1640995200000,  # 2022-01-01 00:00:00 UTC in milliseconds
        "fills": [
            {"price": "50000.00", "qty": "1.00000000", "commission": "0.00100000", "commissionAsset": "BTC"}
        ],
    }


@pytest.fixture
def sample_multiple_fills_response():
    """Create a Binance response with multiple fills."""
    return {
        "symbol": "BTCUSDT",
        "orderId": 123457,
        "transactTime": 1640995200000,
        "fills": [
            {"price": "50000.00", "qty": "0.50000000", "commission": "0.00050000", "commissionAsset": "BTC"},
            {"price": "50010.00", "qty": "0.50000000", "commission": "0.00050000", "commissionAsset": "BTC"},
        ],
    }


class TestOrderExecutor:
    """Test suite for OrderExecutor class."""

    def test_init(self, mock_client):
        """Test OrderExecutor initialization."""
        executor = OrderExecutor(mock_client)
        assert executor.client == mock_client

    @pytest.mark.asyncio
    async def test_execute_order_single_order(
        self, mock_client, sample_order_created_event, sample_binance_response
    ):
        """Test executing a single order successfully."""
        mock_client.create_margin_order.return_value = sample_binance_response

        executor = OrderExecutor(mock_client)

        with patch.object(executor, "publish_transactions") as mock_publish:
            await executor.execute_order(sample_order_created_event)

            # Verify client was called with correct parameters
            mock_client.create_margin_order.assert_called_once_with(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                type="LIMIT",
                quantity=1.0,
                price=50000.0,
                sideEffectType="AUTO_BORROW_REPAY",
                time_in_force="GTC",
            )

            # Verify transaction was published
            mock_publish.assert_called_once()
            transactions = mock_publish.call_args[0][0]
            assert len(transactions) == 1
            assert isinstance(transactions[0], Transaction)

    @pytest.mark.asyncio
    async def test_execute_order_multiple_orders(
        self, mock_client, sample_multiple_orders_event, sample_binance_response
    ):
        """Test executing multiple orders."""
        mock_client.create_margin_order.return_value = sample_binance_response

        executor = OrderExecutor(mock_client)

        with patch.object(executor, "publish_transactions") as mock_publish:
            await executor.execute_order(sample_multiple_orders_event)

            # Verify client was called twice
            assert mock_client.create_margin_order.call_count == 2

            # Verify transactions were published
            mock_publish.assert_called_once()
            transactions = mock_publish.call_args[0][0]
            assert len(transactions) == 2

    @pytest.mark.asyncio
    async def test_execute_order_empty_orders_list(self, mock_client):
        """Test executing with empty orders list raises ValueError."""
        empty_event = OrderCreatedEvent(orders=[])
        executor = OrderExecutor(mock_client)

        with pytest.raises(ValueError, match="No orders to execute"):
            await executor.execute_order(empty_event)

    @pytest.mark.asyncio
    async def test_execute_order_client_exception(self, mock_client, sample_order_created_event):
        """Test handling client exceptions during order execution."""
        mock_client.create_margin_order.side_effect = Exception("API Error")

        executor = OrderExecutor(mock_client)

        with pytest.raises(Exception, match="API Error"):
            await executor.execute_order(sample_order_created_event)

    def test_create_transaction_valid_response(self, mock_client, sample_order, sample_binance_response):
        """Test creating a transaction from a valid response."""
        executor = OrderExecutor(mock_client)
        transaction = executor.create_transaction(sample_order, sample_binance_response)

        assert isinstance(transaction, Transaction)
        assert transaction.order == sample_order
        assert len(transaction.fills) == 1
        assert transaction.fills[0].price == 50000.0
        assert transaction.fills[0].quantity == 1.0
        assert transaction.fills[0].commission == 0.001
        assert transaction.fills[0].commission_asset == "BTC"
        assert transaction.transact_time == datetime(2022, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_create_transaction_multiple_fills(
        self, mock_client, sample_order, sample_multiple_fills_response
    ):
        """Test creating a transaction with multiple fills."""
        executor = OrderExecutor(mock_client)
        transaction = executor.create_transaction(sample_order, sample_multiple_fills_response)

        assert len(transaction.fills) == 2
        assert transaction.fills[0].price == 50000.0
        assert transaction.fills[0].quantity == 0.5
        assert transaction.fills[1].price == 50010.0
        assert transaction.fills[1].quantity == 0.5

    def test_create_transaction_empty_response(self, mock_client, sample_order):
        """Test creating transaction with empty response raises ValueError."""
        executor = OrderExecutor(mock_client)

        with pytest.raises(ValueError, match="Response for order BTCUSDT is invalid"):
            executor.create_transaction(sample_order, {})

    def test_create_transaction_no_fills(self, mock_client, sample_order):
        """Test creating transaction with response missing fills raises ValueError."""
        response = {"symbol": "BTCUSDT", "orderId": 123456}
        executor = OrderExecutor(mock_client)

        with pytest.raises(ValueError, match="Response for order BTCUSDT is invalid"):
            executor.create_transaction(sample_order, response)

    def test_create_transaction_none_response(self, mock_client, sample_order):
        """Test creating transaction with None response raises ValueError."""
        executor = OrderExecutor(mock_client)

        with pytest.raises(ValueError, match="Response for order BTCUSDT is invalid"):
            executor.create_transaction(sample_order, None)

    @pytest.mark.asyncio
    async def test_publish_transactions_single_transaction(
        self, mock_client, sample_order, sample_binance_response
    ):
        """Test publishing a single transaction."""
        executor = OrderExecutor(mock_client)
        transaction = executor.create_transaction(sample_order, sample_binance_response)

        with patch("staarb.core.bus.event_bus.EventBus.publish") as mock_publish:
            await executor.publish_transactions([transaction])

            # Verify publish was called once
            mock_publish.assert_called_once()

            # Verify the event type and content
            event_type, event = mock_publish.call_args[0]
            assert event_type == TransactionClosedEvent
            assert isinstance(event, TransactionClosedEvent)
            assert event.transaction == transaction
            assert event.position_direction == PositionDirection.LONG

    @pytest.mark.asyncio
    async def test_publish_transactions_multiple_transactions(self, mock_client, sample_symbol):
        """Test publishing multiple transactions."""
        executor = OrderExecutor(mock_client)

        # Create transactions with different order sides
        buy_order = Order(symbol=sample_symbol, quantity=1.0, side=OrderSide.BUY)
        sell_order = Order(symbol=sample_symbol, quantity=1.0, side=OrderSide.SELL)

        response = {
            "transactTime": 1640995200000,
            "fills": [{"price": "50000.00", "qty": "1.00", "commission": "0.001", "commissionAsset": "BTC"}],
        }

        buy_transaction = executor.create_transaction(buy_order, response)
        sell_transaction = executor.create_transaction(sell_order, response)

        with patch("staarb.core.bus.event_bus.EventBus.publish") as mock_publish:
            await executor.publish_transactions([buy_transaction, sell_transaction])

            # Verify publish was called twice
            assert mock_publish.call_count == 2

            # Check the position directions are correct
            calls = mock_publish.call_args_list
            buy_event = calls[0][0][1]
            sell_event = calls[1][0][1]

            assert buy_event.position_direction == PositionDirection.LONG
            assert sell_event.position_direction == PositionDirection.SHORT

    @pytest.mark.asyncio
    async def test_publish_transactions_empty_list(self, mock_client):
        """Test publishing empty transactions list."""
        executor = OrderExecutor(mock_client)

        with patch("staarb.core.bus.event_bus.EventBus.publish") as mock_publish:
            await executor.publish_transactions([])

            # Verify publish was not called
            mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_order_integration(
        self, mock_client, sample_order_created_event, sample_binance_response
    ):
        """Test full integration of order execution flow."""
        mock_client.create_margin_order.return_value = sample_binance_response

        executor = OrderExecutor(mock_client)

        with patch("staarb.core.bus.event_bus.EventBus.publish") as mock_publish:
            await executor.execute_order(sample_order_created_event)

            # Verify the complete flow
            mock_client.create_margin_order.assert_called_once()
            mock_publish.assert_called_once()

            # Verify the published event
            event_type, event = mock_publish.call_args[0]
            assert event_type == TransactionClosedEvent
            assert event.transaction.order.symbol.name == "BTCUSDT"
            assert event.position_direction == PositionDirection.LONG

    @pytest.mark.asyncio
    async def test_concurrent_order_execution(
        self, mock_client, sample_multiple_orders_event, sample_binance_response
    ):
        """Test that multiple orders are executed concurrently."""

        # Set up a delay to verify concurrent execution
        async def delayed_response(*_args, **_kwargs):
            await asyncio.sleep(0.1)
            return sample_binance_response

        mock_client.create_margin_order.side_effect = delayed_response

        executor = OrderExecutor(mock_client)

        import time

        start_time = time.time()

        with patch.object(executor, "publish_transactions"):
            await executor.execute_order(sample_multiple_orders_event)

        end_time = time.time()

        # If orders were executed sequentially, this would take ~0.2s
        # If concurrent, it should take ~0.1s
        assert end_time - start_time < 0.15, "Orders should be executed concurrently"
        assert mock_client.create_margin_order.call_count == 2

    def test_create_transaction_data_types(self, mock_client, sample_order):
        """Test that transaction creation handles string-to-float conversion properly."""
        # Modify response to have string values (as they come from API)
        response = {
            "transactTime": 1640995200000,
            "fills": [
                {
                    "price": "50000.50",  # String price
                    "qty": "1.25000000",  # String quantity
                    "commission": "0.00125000",  # String commission
                    "commissionAsset": "BTC",
                }
            ],
        }

        executor = OrderExecutor(mock_client)
        transaction = executor.create_transaction(sample_order, response)

        # Verify proper type conversion
        fill = transaction.fills[0]
        assert isinstance(fill.price, float)
        assert isinstance(fill.quantity, float)
        assert isinstance(fill.commission, float)
        assert fill.price == 50000.5
        assert fill.quantity == 1.25
        assert fill.commission == 0.00125

    @pytest.mark.asyncio
    async def test_order_execution_with_different_order_types(self, mock_client, sample_symbol):
        """Test execution with different order types and parameters."""
        # Test with different order configurations
        orders = [
            Order(symbol=sample_symbol, quantity=1.0, side=OrderSide.BUY, type="MARKET"),
            Order(symbol=sample_symbol, quantity=1.0, side=OrderSide.SELL, type="LIMIT", price=51000.0),
            Order(symbol=sample_symbol, quantity=1.0, side=OrderSide.BUY, type="STOP_LOSS", price=49000.0),
        ]

        event = OrderCreatedEvent(orders=orders)
        mock_client.create_margin_order.return_value = {
            "transactTime": 1640995200000,
            "fills": [{"price": "50000.00", "qty": "1.00", "commission": "0.001", "commissionAsset": "BTC"}],
        }

        executor = OrderExecutor(mock_client)

        with patch.object(executor, "publish_transactions"):
            await executor.execute_order(event)

        # Verify all orders were processed
        assert mock_client.create_margin_order.call_count == 3

        # Check that different order types were called with correct parameters
        calls = mock_client.create_margin_order.call_args_list
        assert calls[0][1]["type"] == "MARKET"
        assert calls[1][1]["type"] == "LIMIT"
        assert calls[1][1]["price"] == 51000.0
        assert calls[2][1]["type"] == "STOP_LOSS"
        assert calls[2][1]["price"] == 49000.0
