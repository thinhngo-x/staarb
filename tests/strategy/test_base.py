"""Tests for base strategy module."""

from abc import ABC

import pytest

from staarb.strategy.base import BaseStrategy


class TestBaseStrategy:
    """Test cases for BaseStrategy abstract class."""

    def test_is_abstract_class(self):
        """Test that BaseStrategy is an abstract class."""
        assert issubclass(BaseStrategy, ABC)

    def test_cannot_instantiate_directly(self):
        """Test that BaseStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseStrategy()

    def test_concrete_implementation_must_implement_generate_signal(self):
        """Test that concrete implementations must implement generate_signal."""

        class IncompleteStrategy(BaseStrategy):
            pass

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_concrete_implementation_works(self):
        """Test that complete concrete implementation works."""

        class ConcreteStrategy(BaseStrategy):
            async def generate_signal(self, market_data: dict) -> dict:  # noqa: ARG002
                return {"signal": "HOLD"}

        # Should be able to instantiate
        strategy = ConcreteStrategy()
        assert isinstance(strategy, BaseStrategy)

    @pytest.mark.asyncio
    async def test_generate_signal_signature(self):
        """Test that generate_signal has correct signature."""

        class TestStrategy(BaseStrategy):
            async def generate_signal(self, market_data: dict) -> dict:  # noqa: ARG002
                return {"signal": "LONG", "confidence": 0.8}

        strategy = TestStrategy()
        result = await strategy.generate_signal({"BTCUSDT": [50000, 51000]})

        assert isinstance(result, dict)
        assert "signal" in result
        assert result["signal"] == "LONG"
