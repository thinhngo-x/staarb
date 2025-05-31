from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
import pytz

from staarb.core.enums import PositionDirection, SessionType, StrategyDecision
from staarb.core.types import HedgeRatio, Order, Transaction

if TYPE_CHECKING:
    from staarb.portfolio.position import Position


@dataclass(kw_only=True)
class BaseEvent:
    timestamp: datetime | None = None
    """Base class for all events in the event bus."""

    def __post_init__(self):
        if self.timestamp is None:
            # Set the timestamp to the current UTC time if not provided
            self.timestamp = datetime.now(tz=pytz.UTC)


@dataclass(kw_only=True)
class SessionEvent(BaseEvent):
    session_type: SessionType
    start_time: datetime
    end_time: datetime | None = None
    session_id: str | None = None
    """Event for session start or end, identified by a session ID."""

    def __post_init__(self):
        super().__post_init__()
        if self.session_id is None:
            # Generate a session ID if not provided
            start_time_str = self.start_time.strftime("%Y%m%d_%H%M%S")
            timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
            self.session_id = f"{self.session_type.value}_{start_time_str}_{timestamp_str}"

    def __repr__(self):
        return f"SessionEvent(timestamp={self.timestamp}, session_type={self.session_type})"


@dataclass(kw_only=True)
class PositionEvent(BaseEvent):
    position: "Position"
    """Event for position updates, such as entry or exit."""

    def __repr__(self):
        return (
            f"PositionEvent(timestamp={self.timestamp}, "
            f"position_id={self.position.position_id}, "
            f"size={self.position.size}, "
            f"direction={self.position.position_direction})"
        )


@dataclass(kw_only=True)
class MarketDataEvent(BaseEvent):
    data: dict[str, pd.Series]
    """Event for market data updates, such as price changes."""

    def __repr__(self):
        if self.data:  # Check if dictionary is not empty
            first_key = next(iter(self.data))
            return (
                f"MarketDataEvent(timestamp={self.timestamp}, "
                f"data=[{type(first_key)} : {type(self.data[first_key])}])"
            )
        return f"MarketDataEvent(timestamp={self.timestamp}, data=empty)"


@dataclass(kw_only=True)
class SignalEvent(BaseEvent):
    signal: StrategyDecision
    hedge_ratio: HedgeRatio
    prices: dict[str, float]


@dataclass(kw_only=True)
class TransactionClosedEvent(BaseEvent):
    transaction: Transaction
    position_direction: PositionDirection
    timestamp: datetime | None = None


@dataclass(kw_only=True)
class OrderCreatedEvent(BaseEvent):
    orders: list[Order]
    timestamp: datetime | None = None
