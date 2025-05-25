from staarb.core.enums import PositionStatus, StrategyDecision


class BollingerBand:
    def __init__(
        self,
        entry_threshold: float = 1.0,
        exit_threshold: float = 0.0,
        *,
        long_only: bool = False,
    ):
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.position = PositionStatus.IDLE
        self.long_only = long_only

    def update_thresholds(self, entry_threshold: float, exit_threshold: float):
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def update_position(self, action: StrategyDecision):
        if action == StrategyDecision.LONG:
            self.position = PositionStatus.LONG
        elif action == StrategyDecision.SHORT:
            self.position = PositionStatus.SHORT
        elif action == StrategyDecision.EXIT:
            self.position = PositionStatus.IDLE

    def generate_signal(self, zscore: float):
        signal = StrategyDecision.HOLD

        if self.position == PositionStatus.IDLE:
            if zscore > self.entry_threshold:
                if not self.long_only:
                    signal = StrategyDecision.SHORT
            elif zscore < -self.entry_threshold:
                signal = StrategyDecision.LONG
        elif self.position == PositionStatus.SHORT:
            if not self.long_only and zscore < self.exit_threshold:
                signal = StrategyDecision.EXIT
        elif self.position == PositionStatus.LONG and zscore > -self.exit_threshold:
            signal = StrategyDecision.EXIT

        return signal
