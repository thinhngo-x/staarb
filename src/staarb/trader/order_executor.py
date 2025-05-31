import asyncio
import logging

from binance.async_client import AsyncClient

from staarb.core.bus.event_bus import EventBus
from staarb.core.bus.events import OrderCreatedEvent, TransactionClosedEvent
from staarb.core.enums import OrderSide, PositionDirection
from staarb.core.types import Fill, Order, Transaction
from staarb.utils import miliseconds_to_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderExecutor:
    def __init__(
        self,
        client: AsyncClient,
    ):
        self.client = client

    async def execute_order(self, order_placed_event: OrderCreatedEvent):
        """
        Execute the given orders.
        """
        orders = order_placed_event.orders
        if not orders:
            msg = "No orders to execute."
            raise ValueError(msg)

        tasks = [
            self.client.create_margin_order(
                symbol=order.symbol.name,
                side=order.side,
                type=order.type,
                quantity=order.quantity,
                price=order.price,
                sideEffectType=order.side_effect,
                time_in_force=order.time_in_force,
            )
            for order in orders
        ]
        responses = await asyncio.gather(*tasks)
        transactions = [
            self.create_transaction(order, response)
            for order, response in zip(orders, responses, strict=True)
        ]
        await self.publish_transactions(transactions)

    async def publish_transactions(self, transactions: list[Transaction]):
        """
        Publish the executed transactions to the event bus.
        """
        transaction_closed_events = [
            TransactionClosedEvent(
                transaction=transaction,
                position_direction=PositionDirection.LONG
                if transaction.order.side == OrderSide.BUY
                else PositionDirection.SHORT,
            )
            for transaction in transactions
        ]
        tasks = [
            asyncio.create_task(EventBus.publish(TransactionClosedEvent, tce))
            for tce in transaction_closed_events
        ]
        await asyncio.gather(*tasks)

    def create_transaction(self, order: Order, response: dict) -> Transaction:
        if not response or "fills" not in response:
            msg = f"Response for order {order.symbol} is invalid: {response}"
            raise ValueError(msg)
        fills = [
            Fill(
                symbol=order.symbol,
                price=float(fill["price"]),
                quantity=float(fill["qty"]),
                commission=float(fill["commission"]),
                commission_asset=fill["commissionAsset"],
            )
            for fill in response["fills"]
        ]
        return Transaction(
            order=order, fills=fills, transact_time=miliseconds_to_date(response["transactTime"])
        )
