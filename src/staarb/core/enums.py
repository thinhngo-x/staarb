from enum import Enum


class PositionDirection(Enum):
    """
    Enum for position directions.
    """

    LONG = "LONG"
    SHORT = "SHORT"


class OrderSide(Enum):
    """
    Enum for order sides.
    """

    BUY = "BUY"
    SELL = "SELL"

    def __str__(self):
        return self.value


class StrategyDecision(Enum):
    """
    Enum for trade signals.
    """

    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    EXIT = "EXIT"


class PositionStatus(Enum):
    """
    Enum for position states.
    """

    LONG = "LONG"
    SHORT = "SHORT"
    IDLE = "IDLE"
