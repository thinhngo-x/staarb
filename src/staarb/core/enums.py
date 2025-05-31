from enum import Enum


class SessionType(str, Enum):
    """Enum for session types."""

    BACKTEST = "backtest"
    LIVE = "live"
    PAPER = "paper"


class PositionDirection(str, Enum):
    """
    Enum for position directions.
    """

    LONG = "LONG"
    SHORT = "SHORT"


class OrderSide(str, Enum):
    """
    Enum for order sides.
    """

    BUY = "BUY"
    SELL = "SELL"


class StrategyDecision(str, Enum):
    """
    Enum for trade signals.
    """

    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    EXIT = "EXIT"


class PositionStatus(str, Enum):
    """
    Enum for position states.
    """

    LONG = "LONG"
    SHORT = "SHORT"
    IDLE = "IDLE"
