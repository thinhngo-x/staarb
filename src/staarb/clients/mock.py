import logging
from typing import TYPE_CHECKING, Any, Literal

from binance.async_client import AsyncClient

from staarb.core.types import DataRequest, LookbackRequest
from staarb.data.exchange_info_fetcher import BinanceExchangeInfo
from staarb.data.ohlc_fetcher import MarketDataFetcher
from staarb.utils import date_to_milliseconds

if TYPE_CHECKING:
    from datetime import datetime

    import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        self._asset_balance: dict[str, Any] = {}
        self.time_stamps: list[datetime] = []

    @classmethod
    async def create(
        cls,
        symbols: list[str],
        dreq: DataRequest | LookbackRequest,
        balance: dict[str, float],
        *args,
        **kwargs,
    ) -> "MockClient":
        client = await super().create(*args, **kwargs)
        client.mock_data = await MarketDataFetcher.fetch_multiple_klines(client, symbols, dreq)
        client.time_stamps = next(iter(client.mock_data.values()), []).index
        client.set_len_data(len(next(iter(client.mock_data.values()), [])))
        for asset, free in balance.items():
            client.gain(asset, free)
        return client

    def gain(self, asset: str, amount: float):
        """
        Set the mock asset balance for a specific asset.
        This simulates the account balance for backtesting.
        Auto repay borrowed amount if the asset is already borrowed.
        """
        msg = f"Adding {amount} {asset} to mock balance."
        logger.info(msg)
        if asset not in self._asset_balance:
            self._asset_balance[asset] = {"free": 0.0, "locked": 0.0, "borrowed": 0.0, "interest": 0.0}
        if self._asset_balance[asset]["borrowed"] > 0:
            loan = self._asset_balance[asset]["borrowed"]
            # If there is a borrowed amount, repay it first
            self._asset_balance[asset]["borrowed"] = max(0.0, loan - amount)
            amount = max(0, amount - loan)
        self._asset_balance[asset]["free"] += amount

    def pay(self, asset: str, amount: float):
        """
        Deduct the specified amount from the mock asset balance.
        This simulates a payment or fee deduction in the mock environment.
        Auto borrow when balance is insufficient.
        """
        msg = f"Paying {amount} {asset} from mock balance."
        logger.info(msg)
        if asset not in self._asset_balance:
            self._asset_balance[asset] = {"free": 0.0, "locked": 0.0, "borrowed": 0.0, "interest": 0.0}
        if self._asset_balance[asset]["free"] < amount:
            self._asset_balance[asset]["borrowed"] += amount - self._asset_balance[asset]["free"]
        self._asset_balance[asset]["free"] = max(0.0, self._asset_balance[asset]["free"] - amount)

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

    async def get_margin_account(self, **_):
        """
        Mock method to simulate getting asset balance.
        This does not make an actual API call but returns the mock asset balance.
        """
        user_assets = []
        for ast, balance in self._asset_balance.items():
            user_assets.append(
                {
                    "asset": ast,
                    "free": str(balance["free"]),
                    "locked": str(balance["locked"]),
                    "borrowed": str(balance["borrowed"]),
                    "interest": str(balance["interest"]),
                }
            )
        return {"userAssets": user_assets}

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
        if side == "BUY":
            self.pay(symbol_info.quote_asset, price * quantity)
            self.gain(symbol_info.base_asset, quantity)
            self.pay(commission_asset, commission)
        else:
            self.pay(symbol_info.base_asset, quantity)
            self.gain(symbol_info.quote_asset, price * quantity)
            self.pay(commission_asset, commission)
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
