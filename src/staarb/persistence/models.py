from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel

from staarb.core.enums import SessionType


class TimestampedModel(SQLModel):
    """Base model with timestamp fields."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )


class TradingSession(TimestampedModel, table=True):
    """Model for a trading session (backtest or live or paper)."""

    session_id: str = Field(primary_key=True)
    session_type: SessionType = Field(default=SessionType.BACKTEST, index=True)
    start_time: datetime
    end_time: datetime | None = Field(default=None, index=True)

    positions: list["Position"] = Relationship(back_populates="session")


class Position(SQLModel, table=True):
    """Model for a trading position."""

    id: str = Field(primary_key=True)
    symbol: str = Field(index=True)
    size: float = 0.0
    is_closed: bool = False

    entry_price: float
    entry_time: datetime

    exit_price: float = Field(default=0.0)
    exit_time: datetime | None = Field(default=None)

    pnl: float = Field(default=0.0)

    session_id: str = Field(foreign_key="tradingsession.session_id", index=True)
    session: TradingSession = Relationship(back_populates="positions")

    transactions: list["Transaction"] = Relationship(back_populates="position")


class Transaction(SQLModel, table=True):
    """Model for a transaction within a position."""

    id: str = Field(primary_key=True)
    timestamp: datetime

    position_id: str = Field(foreign_key="position.id", index=True)
    position: Position = Relationship(back_populates="transactions")

    order: "Order" = Relationship(back_populates="transaction")
    fills: list["Fill"] = Relationship(back_populates="transaction")


class Order(SQLModel, table=True):
    """
    Model for an order within a position.

    Attributes:
        side_effect (str): Default value is "AUTO_BORROW_REPAY".
        time_in_force (str): Default value is "GTC".

    """

    id: int = Field(primary_key=True)
    symbol: str = Field(index=True)
    side: str = Field(index=True)  # e.g., "BUY" or "SELL"
    price: float | None = None
    quantity: float = 0.0
    side_effect: str = Field(default="AUTO_BORROW_REPAY")
    type: str = Field(default="MARKET", index=True)  # e.g., "MARKET", "LIMIT"
    time_in_force: str = Field(default="GTC", index=True)  # e.g., "GTC", "IOC"

    transaction_id: str | None = Field(foreign_key="transaction.id", index=True)
    transaction: "Transaction" = Relationship(back_populates="order")


class Fill(SQLModel, table=True):
    """Model for a fill within a transaction."""

    id: int = Field(primary_key=True)
    symbol: str
    price: float
    quantity: float
    commission: float
    commission_asset: str

    transaction_id: str = Field(foreign_key="transaction.id", index=True)
    transaction: Transaction = Relationship(back_populates="fills")
