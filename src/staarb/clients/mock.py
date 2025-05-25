from typing import TYPE_CHECKING, Literal

from binance.async_client import AsyncClient

from staarb.core.types import DataRequest, LookbackRequest
from staarb.data.exchange_info_fetcher import BinanceExchangeInfo
from staarb.data.ohlc_fetcher import MarketDataFetcher
from staarb.utils import date_to_milliseconds

if TYPE_CHECKING:
    from datetime import datetime

    import pandas as pd


class MockClient(AsyncClient):
    """
    MockClient is a mock client for backtesting purposes.
    It simulates the behavior of the Binance AsyncClient without making actual API calls.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.mock_data: dict[str, pd.Series] = {}  # Store mock data for backtesting
        self._current_pt = 0  # Pointer to the current data point
        self._len_data = 0
        self._commission_rate = 0.001
        self._slippage = 0.001
        self.time_stamps: list[datetime] = []

    @classmethod
    async def create(
        cls, symbols: list[str], dreq: DataRequest | LookbackRequest, *args, **kwargs
    ) -> "MockClient":
        client = await super().create(*args, **kwargs)
        client.mock_data = await MarketDataFetcher.fetch_multiple_klines(client, symbols, dreq)
        client.time_stamps = next(iter(client.mock_data.values()), []).index
        client.set_len_data(len(next(iter(client.mock_data.values()), [])))
        return client

    def set_len_data(self, length: int):
        self._len_data = length

    def set_current_pointer(self, pt: int):
        self._current_pt = pt

    def get_mock_data(self, dreq: LookbackRequest):
        """
        Get mock data for the given lookback request.
        This simulates fetching historical data without making API calls.
        """
        if not self.mock_data:
            msg = "Mock data is not set. Please create the client with mock data first."
            raise ValueError(msg)
        if self._current_pt < dreq.limit:
            msg = f"Current pointer {self._current_pt} is less than the limit {dreq.limit}."
            raise ValueError(msg)

        while self._current_pt < self._len_data:
            self._current_pt += 1
            yield {
                symbol: data[self._current_pt - dreq.limit : self._current_pt]
                for symbol, data in self.mock_data.items()
            }

    def get_current_time(self):
        """
        Get the current mock time.
        This simulates the current time in the mock environment.
        """
        return self.time_stamps[self._current_pt - 1]

    async def create_margin_order(self, symbol: str, quantity: float, side: Literal["BUY", "SELL"], **_):
        """
        Mock method to simulate creating a margin order.
        This does not make an actual API call but simulates the response.
        """
        if symbol not in self.mock_data:
            msg = f"Symbol {symbol} not found in mock data."
            raise ValueError(msg)

        symbol_info = BinanceExchangeInfo.get_symbol_info(symbol)
        price = self.mock_data[symbol].to_numpy()[self._current_pt - 1, 0] * (1 - self._slippage)

        commission_asset = symbol_info.base_asset if side == "BUY" else symbol_info.quote_asset
        commission = (
            quantity * self._commission_rate if side == "BUY" else price * quantity * self._commission_rate
        )
        # Simulate a successful order creation response
        return {
            "symbol": symbol,
            "orderId": 123456789,
            "clientOrderId": "mock_client_order_id",
            "transactTime": date_to_milliseconds(self.get_current_time()),
            "price": None,
            "origQty": quantity,
            "executedQty": quantity,
            "status": "FILLED",
            "fills": [
                {
                    "price": price,
                    "qty": quantity,
                    "commission": commission,
                    "commissionAsset": commission_asset,
                }
            ],
        }
