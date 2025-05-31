import asyncio
import functools as ft
from datetime import UTC, datetime
from decimal import Decimal

import pytz


def round_step_size(quantity: float | Decimal, step_size: str) -> float:
    """
    Rounds a given quantity to a specific step size

    :param quantity: required
    :param step_size: required

    :return: decimal
    """
    quantity = Decimal(str(quantity))
    return float(quantity - quantity % Decimal(step_size))


def date_to_milliseconds(date: datetime):
    """
    Convert a date string to milliseconds since epoch.

    :param date_str: Date string in ISO format or timestamp.
    :return: Milliseconds since epoch.
    """
    if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
        date = date.replace(tzinfo=pytz.utc)
    epoch = datetime.fromtimestamp(0, UTC)
    return int((date - epoch).total_seconds() * 1000.0)


def miliseconds_to_date(milliseconds: int) -> datetime:
    """
    Convert milliseconds since epoch to a datetime object.

    :param milliseconds: Milliseconds since epoch.
    :return: Datetime object in UTC.
    """
    return datetime.fromtimestamp(milliseconds / 1000.0, tz=UTC)


def async_cmd(func):
    @ft.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper
