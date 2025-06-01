"""Tests for statistical arbitrage strategy."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from staarb.core.bus.events import MarketDataEvent, SignalEvent
from staarb.core.enums import StrategyDecision
from staarb.core.types import LookbackRequest, SingleHedgeRatio
from staarb.strategy.statistical_arbitrage import StatisticalArbitrage


class TestStatisticalArbitrage:
    """Test cases for StatisticalArbitrage strategy."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        strategy = StatisticalArbitrage(interval="1h")

        assert strategy.interval == "1h"
        assert strategy.is_fitted is False
        assert strategy.current_signal == StrategyDecision.HOLD

        # Check signal generator defaults
        assert strategy.signal_generator.entry_threshold == 1.0
        assert strategy.signal_generator.exit_threshold == 0.0
        assert strategy.signal_generator.long_only is False

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        hedge_ratio = [
            SingleHedgeRatio(symbol="BTCUSDT", hedge_ratio=1.0),
            SingleHedgeRatio(symbol="ETHUSDT", hedge_ratio=-0.5),
        ]

        strategy = StatisticalArbitrage(
            interval="4h",
            entry_threshold=2.0,
            exit_threshold=0.5,
            hedge_ratio=hedge_ratio,
            num_assets=2,
            half_life_window=50,
            long_only=True,
        )

        assert strategy.interval == "4h"
        assert strategy.signal_generator.entry_threshold == 2.0
        assert strategy.signal_generator.exit_threshold == 0.5
        assert strategy.signal_generator.long_only is True
        assert strategy.signal_model._hedge_ratio == hedge_ratio
        assert strategy.signal_model._num_assets == 2
        assert strategy.signal_model._half_life_window == 50

    def test_get_lookback_request(self):
        """Test getting lookback request."""
        strategy = StatisticalArbitrage(interval="1h")

        # Mock the signal model's get_lookback_window method
        strategy.signal_model.get_lookback_window = MagicMock(return_value=100)

        request = strategy.get_lookback_request()

        assert isinstance(request, LookbackRequest)
        assert request.interval == "1h"
        assert request.limit == 100

    def test_get_hedge_ratio(self):
        """Test getting hedge ratio."""
        hedge_ratio = [
            SingleHedgeRatio(symbol="BTCUSDT", hedge_ratio=1.0),
            SingleHedgeRatio(symbol="ETHUSDT", hedge_ratio=-0.5),
        ]

        strategy = StatisticalArbitrage(interval="1h", hedge_ratio=hedge_ratio)

        result = strategy.get_hedge_ratio()
        assert result == hedge_ratio

    def test_fit_method(self):
        """Test fitting the strategy to market data."""
        strategy = StatisticalArbitrage(interval="1h")

        # Create sample market data
        market_data = {
            "BTCUSDT": pd.Series([50000, 51000, 52000, 53000, 54000]),
            "ETHUSDT": pd.Series([3000, 3100, 3200, 3300, 3400]),
        }

        # Mock the signal model's fit method
        strategy.signal_model.fit = MagicMock()

        strategy.fit(market_data)

        # Check that fit was called and is_fitted is True
        strategy.signal_model.fit.assert_called_once()
        assert strategy.is_fitted is True

        # Check the data format passed to fit
        args, kwargs = strategy.signal_model.fit.call_args
        data, symbols = args
        assert isinstance(data, np.ndarray)
        assert symbols == ["BTCUSDT", "ETHUSDT"]

    @pytest.mark.asyncio
    async def test_on_market_data_not_fitted(self):
        """Test handling market data when strategy is not fitted."""
        strategy = StatisticalArbitrage(interval="1h")

        # Mock methods
        strategy.fit = MagicMock()
        strategy.generate_signal = AsyncMock()

        # Create market data event
        market_data = {"BTCUSDT": pd.Series([50000, 51000, 52000]), "ETHUSDT": pd.Series([3000, 3100, 3200])}
        event = MarketDataEvent(data=market_data)

        await strategy.on_market_data(event)

        # Should call fit first, then generate signal
        strategy.fit.assert_called_once_with(market_data)
        strategy.generate_signal.assert_called_once_with(market_data)

    @pytest.mark.asyncio
    async def test_on_market_data_already_fitted(self):
        """Test handling market data when strategy is already fitted."""
        strategy = StatisticalArbitrage(interval="1h")
        strategy.is_fitted = True

        # Mock methods
        strategy.fit = MagicMock()
        strategy.generate_signal = AsyncMock()

        # Create market data event
        market_data = {"BTCUSDT": pd.Series([50000, 51000, 52000]), "ETHUSDT": pd.Series([3000, 3100, 3200])}
        event = MarketDataEvent(data=market_data)

        await strategy.on_market_data(event)

        # Should not call fit, only generate signal
        strategy.fit.assert_not_called()
        strategy.generate_signal.assert_called_once_with(market_data)

    @pytest.mark.asyncio
    async def test_update_position(self):
        """Test updating position."""
        strategy = StatisticalArbitrage(interval="1h")

        # Mock signal generator
        strategy.signal_generator.update_position = MagicMock()
        strategy.current_signal = StrategyDecision.LONG

        await strategy.update_position()

        strategy.signal_generator.update_position.assert_called_once_with(StrategyDecision.LONG)

    @pytest.mark.asyncio
    @patch("staarb.strategy.statistical_arbitrage.EventBus.publish")
    async def test_generate_signal(self, mock_publish):
        """Test signal generation."""
        strategy = StatisticalArbitrage(interval="1h")

        # Mock dependencies
        strategy.signal_model.estimate = MagicMock(return_value=1.5)
        strategy.signal_generator.generate_signal = MagicMock(return_value=StrategyDecision.SHORT)
        strategy.get_hedge_ratio = MagicMock(
            return_value=[
                SingleHedgeRatio(symbol="BTCUSDT", hedge_ratio=1.0),
                SingleHedgeRatio(symbol="ETHUSDT", hedge_ratio=-0.5),
            ]
        )

        # Create market data
        market_data = {
            "BTCUSDT": pd.DataFrame([[55000, 0], [56000, 1]], columns=["close", "index"])[["close"]],
            "ETHUSDT": pd.DataFrame([[3500, 0], [3600, 1]], columns=["close", "index"])[["close"]],
        }

        await strategy.generate_signal(market_data)

        # Check that estimate was called
        strategy.signal_model.estimate.assert_called_once()

        # Check that signal was generated
        strategy.signal_generator.generate_signal.assert_called_once_with(1.5)

        # Check current signal was updated
        assert strategy.current_signal == StrategyDecision.SHORT

        # Check that event was published
        mock_publish.assert_called_once()
        args, kwargs = mock_publish.call_args
        assert args[0] == SignalEvent
        signal_event = args[1]
        assert signal_event.signal == StrategyDecision.SHORT
        assert signal_event.prices == {"BTCUSDT": 56000, "ETHUSDT": 3600}

    @pytest.mark.asyncio
    async def test_integration_workflow(self):
        """Test complete workflow from market data to signal generation."""
        strategy = StatisticalArbitrage(interval="1h", entry_threshold=1.0, exit_threshold=0.0)

        # Create synthetic cointegrated data
        np.random.seed(42)
        n = 50
        common_trend = np.cumsum(np.random.normal(0, 1, n))
        series1 = common_trend + np.random.normal(0, 0.1, n)
        series2 = 2 * common_trend + 1 + np.random.normal(0, 0.1, n)

        market_data = {
            "BTCUSDT": pd.DataFrame([[v, i] for i, v in enumerate(series1)], columns=["close", "index"])[
                ["close"]
            ],
            "ETHUSDT": pd.DataFrame([[v, i] for i, v in enumerate(series2)], columns=["close", "index"])[
                ["close"]
            ],
        }

        # Mock EventBus to avoid actual publishing
        with patch("staarb.strategy.statistical_arbitrage.EventBus.publish") as mock_publish:
            event = MarketDataEvent(data=market_data)
            await strategy.on_market_data(event)

            # Strategy should be fitted after first call
            assert strategy.is_fitted is True

            # Signal should be generated
            mock_publish.assert_called_once()

    def test_signal_model_initialization(self):
        """Test that signal model is properly initialized."""
        hedge_ratio = [
            SingleHedgeRatio(symbol="BTCUSDT", hedge_ratio=1.0),
            SingleHedgeRatio(symbol="ETHUSDT", hedge_ratio=-0.5),
        ]

        strategy = StatisticalArbitrage(
            interval="1h", hedge_ratio=hedge_ratio, num_assets=2, half_life_window=30
        )

        # Check that Johansen model was initialized with correct parameters
        assert strategy.signal_model._hedge_ratio == hedge_ratio
        assert strategy.signal_model._num_assets == 2
        assert strategy.signal_model._half_life_window == 30

    def test_signal_generator_initialization(self):
        """Test that signal generator is properly initialized."""
        strategy = StatisticalArbitrage(
            interval="1h", entry_threshold=2.5, exit_threshold=0.3, long_only=True
        )

        # Check that Bollinger Band generator was initialized with correct parameters
        assert strategy.signal_generator.entry_threshold == 2.5
        assert strategy.signal_generator.exit_threshold == 0.3
        assert strategy.signal_generator.long_only is True

    @pytest.mark.parametrize(
        ("interval", "expected"),
        [
            ("1m", "1m"),
            ("5m", "5m"),
            ("1h", "1h"),
            ("1d", "1d"),
        ],
    )
    def test_interval_parameter(self, interval, expected):
        """Test that interval parameter is stored correctly."""
        strategy = StatisticalArbitrage(interval=interval)
        assert strategy.interval == expected

    def test_current_signal_initial_state(self):
        """Test that current signal starts as HOLD."""
        strategy = StatisticalArbitrage(interval="1h")
        assert strategy.current_signal == StrategyDecision.HOLD
