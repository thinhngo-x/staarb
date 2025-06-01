"""Tests for signal generator module."""

import pytest

from staarb.core.enums import PositionStatus, StrategyDecision
from staarb.strategy.signal_generator import BollingerBand


class TestBollingerBand:
    """Test cases for BollingerBand signal generator."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        bb = BollingerBand()
        assert bb.entry_threshold == 1.0
        assert bb.exit_threshold == 0.0
        assert bb.position == PositionStatus.IDLE
        assert bb.long_only is False

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        bb = BollingerBand(entry_threshold=2.0, exit_threshold=0.5, long_only=True)
        assert bb.entry_threshold == 2.0
        assert bb.exit_threshold == 0.5
        assert bb.position == PositionStatus.IDLE
        assert bb.long_only is True

    def test_update_thresholds(self):
        """Test updating entry and exit thresholds."""
        bb = BollingerBand(entry_threshold=1.0, exit_threshold=0.0)
        bb.update_thresholds(2.5, 0.5)
        assert bb.entry_threshold == 2.5
        assert bb.exit_threshold == 0.5

    def test_update_position_long(self):
        """Test updating position to LONG."""
        bb = BollingerBand()
        bb.update_position(StrategyDecision.LONG)
        assert bb.position == PositionStatus.LONG

    def test_update_position_short(self):
        """Test updating position to SHORT."""
        bb = BollingerBand()
        bb.update_position(StrategyDecision.SHORT)
        assert bb.position == PositionStatus.SHORT

    def test_update_position_exit(self):
        """Test updating position to IDLE on exit."""
        bb = BollingerBand()
        bb.position = PositionStatus.LONG
        bb.update_position(StrategyDecision.EXIT)
        assert bb.position == PositionStatus.IDLE

    def test_generate_signal_idle_long_entry(self):
        """Test generating LONG signal when idle and zscore below negative threshold."""
        bb = BollingerBand(entry_threshold=1.0)
        signal = bb.generate_signal(-1.5)  # Below -entry_threshold
        assert signal == StrategyDecision.LONG

    def test_generate_signal_idle_short_entry(self):
        """Test generating SHORT signal when idle and zscore above threshold."""
        bb = BollingerBand(entry_threshold=1.0)
        signal = bb.generate_signal(1.5)  # Above entry_threshold
        assert signal == StrategyDecision.SHORT

    def test_generate_signal_idle_no_entry(self):
        """Test no signal when zscore is within thresholds."""
        bb = BollingerBand(entry_threshold=1.0)
        signal = bb.generate_signal(0.5)  # Within thresholds
        assert signal == StrategyDecision.HOLD

    def test_generate_signal_long_exit(self):
        """Test generating EXIT signal when in LONG position."""
        bb = BollingerBand(exit_threshold=0.0)
        bb.position = PositionStatus.LONG
        signal = bb.generate_signal(0.1)  # Above -exit_threshold
        assert signal == StrategyDecision.EXIT

    def test_generate_signal_long_no_exit(self):
        """Test no exit signal when in LONG position and conditions not met."""
        bb = BollingerBand(exit_threshold=0.5)
        bb.position = PositionStatus.LONG
        signal = bb.generate_signal(-0.6)  # Below -exit_threshold
        assert signal == StrategyDecision.HOLD

    def test_generate_signal_short_exit(self):
        """Test generating EXIT signal when in SHORT position."""
        bb = BollingerBand(exit_threshold=0.0)
        bb.position = PositionStatus.SHORT
        signal = bb.generate_signal(-0.1)  # Below exit_threshold
        assert signal == StrategyDecision.EXIT

    def test_generate_signal_short_no_exit(self):
        """Test no exit signal when in SHORT position and conditions not met."""
        bb = BollingerBand(exit_threshold=0.5)
        bb.position = PositionStatus.SHORT
        signal = bb.generate_signal(0.6)  # Above exit_threshold
        assert signal == StrategyDecision.HOLD

    def test_long_only_mode_no_short(self):
        """Test that SHORT signals are not generated in long_only mode."""
        bb = BollingerBand(entry_threshold=1.0, long_only=True)
        signal = bb.generate_signal(1.5)  # Would normally trigger SHORT
        assert signal == StrategyDecision.HOLD

    def test_long_only_mode_allows_long(self):
        """Test that LONG signals are still generated in long_only mode."""
        bb = BollingerBand(entry_threshold=1.0, long_only=True)
        signal = bb.generate_signal(-1.5)  # Should trigger LONG
        assert signal == StrategyDecision.LONG

    def test_long_only_mode_short_position_no_exit(self):
        """Test that SHORT position doesn't exit in long_only mode."""
        bb = BollingerBand(exit_threshold=0.0, long_only=True)
        bb.position = PositionStatus.SHORT
        signal = bb.generate_signal(-0.1)  # Would normally trigger exit
        assert signal == StrategyDecision.HOLD

    @pytest.mark.parametrize(
        ("zscore", "expected_signal"),
        [
            (-2.0, StrategyDecision.LONG),
            (-1.1, StrategyDecision.LONG),
            (-1.0, StrategyDecision.HOLD),  # Exact threshold doesn't trigger (uses <, not <=)
            (-0.5, StrategyDecision.HOLD),
            (0.0, StrategyDecision.HOLD),
            (0.5, StrategyDecision.HOLD),
            (1.0, StrategyDecision.HOLD),  # Exact threshold doesn't trigger (uses >, not >=)
            (1.1, StrategyDecision.SHORT),
            (2.0, StrategyDecision.SHORT),
        ],
    )
    def test_generate_signal_parametrized(self, zscore, expected_signal):
        """Test signal generation with various zscore values."""
        bb = BollingerBand(entry_threshold=1.0)
        signal = bb.generate_signal(zscore)
        assert signal == expected_signal

    def test_edge_case_exact_threshold_values(self):
        """Test behavior at exact threshold values."""
        bb = BollingerBand(entry_threshold=1.0, exit_threshold=0.0)

        # Exact entry threshold should NOT trigger signals (strict inequalities)
        signal = bb.generate_signal(1.0)
        assert signal == StrategyDecision.HOLD

        signal = bb.generate_signal(-1.0)
        assert signal == StrategyDecision.HOLD

        # Just above/below thresholds should trigger
        signal = bb.generate_signal(1.1)
        assert signal == StrategyDecision.SHORT

        signal = bb.generate_signal(-1.1)
        assert signal == StrategyDecision.LONG

        # Exact exit threshold
        bb.position = PositionStatus.LONG
        signal = bb.generate_signal(0.1)  # Above -exit_threshold (0.0)
        assert signal == StrategyDecision.EXIT
