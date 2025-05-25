from staarb.core.bus.events import TransactionClosedEvent
from staarb.core.enums import OrderSide, PositionDirection
from staarb.core.types import Symbol, Transaction


class Position:
    """A class to manage a trading position."""

    position_direction: PositionDirection

    def __init__(self, symbol: Symbol, size: float = 0):
        self.symbol = symbol
        self.size = size
        self.entry_price = 0.0
        self.exit_price = 0.0
        self.pnl = 0.0
        self.is_closed = False
        self.transaction_history: list[Transaction] = []

    def update_position(self, transaction_closed_event: TransactionClosedEvent):
        """Update the position with a new transaction."""
        transaction = transaction_closed_event.transaction
        if not hasattr(self, "position_direction"):
            is_entry = True
            self.position_direction = transaction_closed_event.position_direction
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
            self.close_position(exit_price)

    def close_position(self, exit_price: float):
        """Close the position at the given exit price."""
        if self.size == 0:
            msg = "Cannot close a position with size 0."
            raise ValueError(msg)
        self.exit_price = exit_price
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
