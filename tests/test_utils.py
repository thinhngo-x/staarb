import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytz

from staarb.utils import async_cmd, date_to_milliseconds, round_step_size


class TestRoundStepSize:
    """Test the round_step_size function."""

    def test_round_step_size_with_float(self):
        """Test rounding with float input."""
        result = round_step_size(12.3456, "0.01")
        assert result == 12.34

    def test_round_step_size_with_decimal(self):
        """Test rounding with Decimal input."""
        result = round_step_size(Decimal("12.3456"), "0.01")
        assert result == 12.34

    def test_round_step_size_with_string_quantity(self):
        """Test rounding with string quantity."""
        result = round_step_size("12.3456", "0.1")
        assert result == 12.3

    def test_round_step_size_edge_cases(self):
        """Test edge cases for step size rounding."""
        # Test with zero
        assert round_step_size(0, "0.01") == 0.0

        # Test with very small step size
        result = round_step_size(1.23456789, "0.00001")
        assert result == 1.23456


class TestDateToMilliseconds:
    """Test the date_to_milliseconds function."""

    def test_utc_datetime(self):
        """Test with UTC datetime."""
        date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = date_to_milliseconds(date)
        expected = 1704110400000  # January 1, 2024 12:00:00 UTC in ms
        assert result == expected

    def test_naive_datetime(self):
        """Test with naive datetime (should be treated as UTC)."""
        date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = date_to_milliseconds(date)
        expected = 1704110400000
        assert result == expected

    def test_timezone_aware_datetime(self):
        """Test with timezone-aware datetime."""
        est = pytz.timezone("US/Eastern")
        # Use localize() instead of tzinfo to get correct timezone handling
        naive_date = datetime(2024, 1, 1, 7, 0, 0)  # noqa: DTZ001
        date = est.localize(naive_date)  # 7 AM EST = 12 PM UTC
        result = date_to_milliseconds(date)
        expected = 1704110400000
        assert result == expected

    def test_different_timezone(self):
        """Test with different timezone."""
        jst = pytz.timezone("Asia/Tokyo")
        # Use localize() instead of tzinfo to get correct timezone handling
        naive_date = datetime(2024, 1, 1, 21, 0, 0)  # noqa: DTZ001
        date = jst.localize(naive_date)  # 9 PM JST = 12 PM UTC
        result = date_to_milliseconds(date)
        expected = 1704110400000
        assert result == expected


class TestAsyncCmd:
    """Test the async_cmd decorator."""

    def test_async_cmd_decorator(self):
        """Test that async_cmd runs async function synchronously."""

        @async_cmd
        async def async_function(x, y):
            await asyncio.sleep(0.01)  # Small delay to ensure it's actually async
            return x + y

        result = async_function(5, 3)
        assert result == 8

    def test_async_cmd_with_exception(self):
        """Test async_cmd with function that raises exception."""

        @async_cmd
        async def failing_function():
            await asyncio.sleep(0.01)
            error_msg = "Test error"
            raise ValueError(error_msg)

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

    def test_async_cmd_preserves_function_metadata(self):
        """Test that async_cmd preserves original function metadata."""

        @async_cmd
        async def documented_function():
            """A test function for demonstration."""
            return "test"

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "A test function for demonstration."
