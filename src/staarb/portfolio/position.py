import uuid
from datetime import UTC, datetime

from staarb.core.bus.event_bus import EventBus
from staarb.core.bus.events import PositionEvent, TransactionClosedEvent
from staarb.core.enums import OrderSide, PositionDirection
from staarb.core.types import Symbol, Transaction


class Position:
    """A class to manage a trading position."""

    position_direction: PositionDirection

    def __init__(self, symbol: Symbol, size: float = 0, position_id: str | None = None):
        self.symbol = symbol
        self.size = size
        self.entry_price = 0.0
        self.entry_time = datetime.now(tz=UTC)
        self.exit_time: datetime | None = None
        self.exit_price = 0.0
        self.pnl = 0.0
        self.is_closed = False
        self.transaction_history: list[Transaction] = []
        self.position_id = position_id or self._generate_position_id()
        self._save_transaction_count = 0

    def _generate_position_id(self) -> str:
        """Generate a unique position ID."""
        return str(uuid.uuid4())

    def mark_transactions_as_saved(self, count: int):
        """Mark transactions as saved by incrementing the save transaction count."""
        self._save_transaction_count += count

    def get_unsaved_transactions(self) -> list[Transaction]:
        """Get the list of transactions that have not been saved yet."""
        return self.transaction_history[self._save_transaction_count :]

    async def publish_position(self):
        await EventBus.publish(PositionEvent, PositionEvent(position=self))

    def update_position(self, transaction_closed_event: TransactionClosedEvent):
        """Update the position with a new transaction."""
        transaction = transaction_closed_event.transaction
        if not hasattr(self, "position_direction"):
            is_entry = True
            self.position_direction = transaction_closed_event.position_direction
            self.entry_time = transaction.transact_time
        elif self.position_direction == transaction_closed_event.position_direction:
            is_entry = True  # Same direction, so it's an entry in a multi-entry position
        else:
            is_entry = False  # Different direction, so it's an exit
        self.transaction_history.append(transaction)

        if transaction.order.symbol != self.symbol:
            msg = (
                f"Transaction symbol {transaction.order.symbol} does not match position symbol {self.symbol}"
            )
            raise ValueError(msg)

        # Calculate the signed quantity based on order side
        base_quantity = sum(fill.base_quantity for fill in transaction.fills)
        signed_quantity = base_quantity if transaction.order.side == OrderSide.BUY else -base_quantity

        if is_entry:
            self.size += signed_quantity
            # For entry, calculate weighted average entry price
            total_quote = sum(fill.quote_quantity for fill in transaction.fills)
            if self.size != 0:
                self.entry_price = total_quote / abs(self.size)
        else:
            exit_quote = sum(fill.quote_quantity for fill in transaction.fills)
            exit_price = exit_quote / abs(signed_quantity)
            self.close_position(exit_price, transaction.transact_time)

    def close_position(self, exit_price: float, exit_time: datetime):
        """Close the position at the given exit price."""
        if self.size == 0:
            msg = "Cannot close a position with size 0."
            raise ValueError(msg)
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.pnl = self.calculate_pnl()
        self.is_closed = True

    def calculate_pnl(self) -> float:
        """Calculate the profit and loss of the position."""
        if self.size == 0:
            return 0.0

        if self.exit_price > 0:
            # For long positions (size > 0): PnL = (exit_price - entry_price) * size
            # For short positions (size < 0): PnL = (entry_price - exit_price) * abs(size)
            # This can be simplified to: (exit_price - entry_price) * size
            return (self.exit_price - self.entry_price) * self.size
        return 0.0

    def __repr__(self):
        return (
            f"Position(symbol={self.symbol}, size={self.size}, entry_price={self.entry_price}, "
            f"entry_time={self.entry_time}, exit_time={self.exit_time}, exit_price={self.exit_price}, "
            f"pnl={self.pnl}, is_closed={self.is_closed}, position_id={self.position_id})"
        )
