"""Tests for Johansen cointegration model."""

import numpy as np
import pytest

from staarb.core.types import SingleHedgeRatio
from staarb.strategy.johansen_model import JohansenCointegrationModel


class TestJohansenCointegrationModel:
    """Test cases for JohansenCointegrationModel."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        model = JohansenCointegrationModel()
        assert model._hedge_ratio is None
        assert model._num_assets is None
        assert model._half_life_window is None

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        hedge_ratio = [
            SingleHedgeRatio(symbol="BTCUSDT", hedge_ratio=1.0),
            SingleHedgeRatio(symbol="ETHUSDT", hedge_ratio=-0.5),
        ]
        model = JohansenCointegrationModel(hedge_ratio=hedge_ratio, num_assets=2, half_life_window=50)
        assert model._hedge_ratio == hedge_ratio
        assert model._num_assets == 2
        assert model._half_life_window == 50

    def test_get_lookback_window(self):
        """Test getting lookback window."""
        model = JohansenCointegrationModel(half_life_window=30)
        assert model.get_lookback_window() == 30

    def test_get_lookback_window_none(self):
        """Test getting lookback window when None."""
        model = JohansenCointegrationModel()
        assert model.get_lookback_window() is None

    def test_hedge_ratio_property_not_fitted(self):
        """Test hedge ratio property raises error when not fitted."""
        model = JohansenCointegrationModel()
        with pytest.raises(ValueError, match="Hedge ratio is not fitted yet"):
            _ = model.hedge_ratio

    def test_hedge_ratio_property_fitted(self):
        """Test hedge ratio property returns copy when fitted."""
        hedge_ratio = [
            SingleHedgeRatio(symbol="BTCUSDT", hedge_ratio=1.0),
            SingleHedgeRatio(symbol="ETHUSDT", hedge_ratio=-0.5),
        ]
        model = JohansenCointegrationModel(hedge_ratio=hedge_ratio)
        result = model.hedge_ratio
        assert result == hedge_ratio
        assert result is not hedge_ratio  # Should be a copy

    def test_fit_with_synthetic_data(self):
        """Test fitting with synthetic cointegrated data."""
        model = JohansenCointegrationModel()

        # Create synthetic cointegrated time series
        np.random.seed(42)
        n = 100

        # Create a common trend
        common_trend = np.cumsum(np.random.normal(0, 1, n))

        # Create two series that follow the common trend with some noise
        series1 = common_trend + np.random.normal(0, 0.1, n)
        series2 = 2 * common_trend + 1 + np.random.normal(0, 0.1, n)

        data = np.array([series1, series2])
        symbols = ["BTCUSDT", "ETHUSDT"]

        model.fit(data, symbols)

        # Check that model is fitted
        assert model._hedge_ratio is not None
        assert model._num_assets == 2
        assert model._half_life_window is not None
        assert len(model._hedge_ratio) == 2

        # Check hedge ratio structure
        assert model._hedge_ratio[0].symbol == "BTCUSDT"
        assert model._hedge_ratio[1].symbol == "ETHUSDT"

        # Check that hedge ratio is normalized (first component should be 1.0)
        assert model._hedge_ratio[0].hedge_ratio == 1.0

    def test_estimate_not_fitted(self):
        """Test estimate raises error when not fitted."""
        model = JohansenCointegrationModel()
        data = np.random.rand(2, 50)

        with pytest.raises(ValueError, match="Hedge ratio is not fitted yet"):
            model.estimate(data)

    def test_estimate_no_half_life(self):
        """Test estimate raises error when half life not fitted."""
        hedge_ratio = [
            SingleHedgeRatio(symbol="BTCUSDT", hedge_ratio=1.0),
            SingleHedgeRatio(symbol="ETHUSDT", hedge_ratio=-0.5),
        ]
        model = JohansenCointegrationModel(hedge_ratio=hedge_ratio)
        data = np.random.rand(2, 50)

        with pytest.raises(ValueError, match="Half life window is not fitted yet"):
            model.estimate(data)

    def test_estimate_with_fitted_model(self):
        """Test estimate with fitted model."""
        # Create a fitted model
        hedge_ratio = [
            SingleHedgeRatio(symbol="BTCUSDT", hedge_ratio=1.0),
            SingleHedgeRatio(symbol="ETHUSDT", hedge_ratio=-0.5),
        ]
        model = JohansenCointegrationModel(hedge_ratio=hedge_ratio, half_life_window=20)

        # Create test data
        np.random.seed(42)
        data = np.random.rand(2, 50)

        zscore = model.estimate(data)

        assert isinstance(zscore, float)
        assert not np.isnan(zscore)

    def test_analyze_with_synthetic_data(self):
        """Test analyze method with synthetic cointegrated data."""
        model = JohansenCointegrationModel()

        # Create synthetic cointegrated data
        np.random.seed(42)
        n = 100
        common_trend = np.cumsum(np.random.normal(0, 1, n))
        series1 = common_trend + np.random.normal(0, 0.1, n)
        series2 = 2 * common_trend + 1 + np.random.normal(0, 0.1, n)
        data = np.array([series1, series2])

        (trace_stat, trace_crit_vals, eig_stat, eig_crit_vals, adf_p_value, spread) = model.analyze(data)

        # Check return types and shapes
        assert isinstance(trace_stat, (float, np.floating))
        assert isinstance(trace_crit_vals, np.ndarray)
        assert len(trace_crit_vals) == 3  # 90%, 95%, 99% critical values
        assert isinstance(eig_stat, (float, np.floating))
        assert isinstance(eig_crit_vals, np.ndarray)
        assert len(eig_crit_vals) == 3
        assert isinstance(adf_p_value, (float, np.floating))
        assert isinstance(spread, np.ndarray)
        assert len(spread) == n

    @pytest.fixture
    def fitted_model(self):
        """Create a fitted model for testing."""
        hedge_ratio = [
            SingleHedgeRatio(symbol="BTCUSDT", hedge_ratio=1.0),
            SingleHedgeRatio(symbol="ETHUSDT", hedge_ratio=-0.5),
        ]
        return JohansenCointegrationModel(hedge_ratio=hedge_ratio, num_assets=2, half_life_window=20)

    def test_vec_hedge_ratio_creation(self, fitted_model):
        """Test that vector hedge ratio is created on first estimate call."""
        data = np.random.rand(2, 30)

        # Vector hedge ratio should not exist initially
        assert not hasattr(fitted_model, "_vec_hedge_ratio")

        # After first estimate call, it should be created
        fitted_model.estimate(data)
        assert hasattr(fitted_model, "_vec_hedge_ratio")
        assert fitted_model._vec_hedge_ratio.shape == (2,)
        assert fitted_model._vec_hedge_ratio[0] == 1.0
        assert fitted_model._vec_hedge_ratio[1] == -0.5

    def test_estimate_uses_half_life_window(self, fitted_model):
        """Test that estimate uses the correct number of data points."""
        # Create data with more points than half life window
        data = np.random.rand(2, 50)
        fitted_model._half_life_window = 10

        # Mock the vector hedge ratio to avoid creation
        fitted_model._vec_hedge_ratio = np.array([1.0, -0.5])

        zscore = fitted_model.estimate(data)

        # Should use only the last half_life_window points
        assert isinstance(zscore, float)
