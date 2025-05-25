import numpy as np
from pandas import Series

from staarb.core.bus.event_bus import EventBus
from staarb.core.bus.events import MarketDataEvent, SignalEvent
from staarb.core.types import HedgeRatio, LookbackRequest
from staarb.strategy.base import BaseStrategy
from staarb.strategy.johansen_model import JohansenCointegrationModel
from staarb.strategy.signal_generator import BollingerBand


class StatisticalArbitrage(BaseStrategy):
    def __init__(  # noqa: PLR0913
        self,
        interval: str,
        entry_threshold: float = 1.0,
        exit_threshold: float = 0.0,
        *,
        hedge_ratio: HedgeRatio | None = None,
        num_assets: int | None = None,
        half_life_window: int | None = None,
        long_only: bool = False,
    ):
        self.signal_model = JohansenCointegrationModel(
            hedge_ratio=hedge_ratio,
            num_assets=num_assets,
            half_life_window=half_life_window,
        )
        self.signal_generator = BollingerBand(
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            long_only=long_only,
        )
        self.is_fitted = False
        self.interval = interval

    def get_lookback_request(self) -> LookbackRequest:
        """
        Get the lookback request for the strategy.

        Returns:
            A LookbackRequest object containing the required lookback data.

        """
        return LookbackRequest(self.interval, limit=self.signal_model.get_lookback_window())

    def get_hedge_ratio(self):
        """
        Get the hedge ratio from the signal model.

        Returns:
            The hedge ratio.

        """
        return self.signal_model.get_hedge_ratio()

    def fit(self, market_data: dict[str, Series]):
        """
        Fit the signal model to the market data.

        Args:
            market_data: A dictionary containing market data for each asset.

        """
        # Convert market data to a 2D array
        data = np.concat([market_data[symbol].to_numpy().T for symbol in market_data], axis=0)

        # Fit the signal model
        self.signal_model.fit(data, list(market_data.keys()))
        self.is_fitted = True

    async def on_market_data(self, market_data_event: MarketDataEvent):
        """
        Handle market data events and generate trading signals.

        Args:
            market_data_event: The market data event containing prices for each asset.

        """
        # Extract market data from the event
        market_data = market_data_event.data

        # Fit the model if not already fitted
        if not self.is_fitted:
            self.fit(market_data)

        # Generate the trading signal
        await self.generate_signal(market_data)

    async def generate_signal(self, market_data: dict[str, Series]):
        """
        Generate a trading signal based on the market data.

        Args:
            market_data: A dictionary containing market data for each asset.

        Returns:
            A dictionary containing the generated trading signal.

        """
        # Convert market data to a 2D array
        data = np.concat([market_data[symbol].to_numpy().T for symbol in market_data], axis=0)

        # Calculate the z-score
        zscore = self.signal_model.estimate(data)

        # Generate the trading signal
        signal = self.signal_generator.generate_signal(zscore)
        prices = {symbol: market_data[symbol].to_numpy()[-1][0] for symbol in market_data}

        await EventBus.publish(
            SignalEvent, SignalEvent(signal=signal, hedge_ratio=self.get_hedge_ratio(), prices=prices)
        )
