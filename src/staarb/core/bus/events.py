from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import pytz

from staarb.core.enums import PositionDirection, StrategyDecision
from staarb.core.types import HedgeRatio, Order, Transaction


@dataclass(kw_only=True)
class BaseEvent:
    timestamp: datetime | None = None
    """Base class for all events in the event bus."""

    def __post_init__(self):
        if self.timestamp is None:
            # Set the timestamp to the current UTC time if not provided
            self.timestamp = datetime.now(tz=pytz.UTC)


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
