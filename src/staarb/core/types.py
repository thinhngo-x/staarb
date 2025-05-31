import uuid
from dataclasses import dataclass
from datetime import datetime

from staarb.core.enums import OrderSide


@dataclass
class LotSizeFilter:
    min_qty: str
    max_qty: str
    step_size: str


@dataclass
class PriceFilter:
    min_price: str
    max_price: str
    tick_size: str


@dataclass
class NotionalFitter:
    min_notional: str
    max_notional: str


@dataclass
class Filters:
    lot_size: LotSizeFilter
    price: PriceFilter
    notional: NotionalFitter

    def __init__(self, *filters):
        for filter_config in filters:
            if filter_config["filterType"] == "LOT_SIZE":
                self.lot_size = LotSizeFilter(
                    min_qty=filter_config["minQty"],
                    max_qty=filter_config["maxQty"],
                    step_size=filter_config["stepSize"],
                )
            elif filter_config["filterType"] == "PRICE_FILTER":
                self.price = PriceFilter(
                    min_price=filter_config["minPrice"],
                    max_price=filter_config["maxPrice"],
                    tick_size=filter_config["tickSize"],
                )
            elif filter_config["filterType"] == "NOTIONAL":
                self.notional = NotionalFitter(
                    min_notional=filter_config["minNotional"], max_notional=filter_config["maxNotional"]
                )


@dataclass
class Symbol:
    name: str
    base_asset: str
    quote_asset: str
    base_asset_precision: int
    quote_asset_precision: int
    filters: Filters

    def __init__(self, **kwargs):
        self.name = kwargs.get("symbol")
        self.base_asset = kwargs.get("baseAsset")
        self.quote_asset = kwargs.get("quoteAsset")
        self.base_asset_precision = kwargs.get("baseAssetPrecision")
        self.quote_asset_precision = kwargs.get("quoteAssetPrecision")
        self.filters = Filters(*kwargs.get("filters"))

    def __eq__(self, value):
        if not isinstance(value, Symbol):
            msg = f"Cannot compare {self.__class__.__name__} with {value.__class__.__name__}"
            raise TypeError(msg)
        return self.name == value.name

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"Symbol(name={self.name}, ...)"

    def __hash__(self):
        return hash(self.name)


@dataclass
class DataRequest:
    interval: str
    start: int
    end: int
    columns: list[str] | None = None

    def __post_init__(self):
        if self.columns is None:
            self.columns = ["close"]


@dataclass
class LookbackRequest:
    interval: str
    limit: int
    columns: list[str] | None = None

    def __post_init__(self):
        if self.columns is None:
            self.columns = ["close"]


KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
]


@dataclass
class SingleHedgeRatio:
    symbol: str
    hedge_ratio: float


HedgeRatio = list[SingleHedgeRatio]


class Fill:
    """A class to represent a trade fill."""

    symbol: Symbol
    price: float
    quantity: float
    commission: float
    commission_asset: str
    base_quantity: float
    quote_quantity: float

    def __init__(
        self, symbol: Symbol, price: float, quantity: float, commission: float, commission_asset: str
    ):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.commission = commission
        self.commission_asset = commission_asset
        self.base_quantity = self._set_base_quantity()
        self.quote_quantity = self._set_quote_quantity()

    def _set_quote_quantity(self):
        if self.symbol.quote_asset == self.commission_asset:
            return self.price * self.quantity - self.commission
        return self.price * self.quantity

    def _set_base_quantity(self):
        if self.symbol.base_asset == self.commission_asset:
            return self.quantity - self.commission
        return self.quantity


@dataclass
class Order:
    symbol: Symbol
    quantity: float
    side: OrderSide
    price: float | None = None
    side_effect: str = "AUTO_BORROW_REPAY"
    type: str = "MARKET"
    time_in_force: str = "GTC"


@dataclass
class Transaction:
    order: Order
    fills: list[Fill]
    transact_time: datetime
    id: str | None = None

    def __post_init__(self):
        if not self.fills:
            msg = "Transaction must have at least one fill."
            raise ValueError(msg)
        if not isinstance(self.fills, list):
            msg = f"Transaction fills must be a list, got {type(self.fills)}"
            raise TypeError(msg)
        if self.order.symbol != self.fills[0].symbol:
            msg = f"Order symbol {self.order.symbol} does not match fill symbol {self.fills[0].symbol.name}"
            raise ValueError(msg)
        if self.id is None:
            self.id = str(uuid.uuid4())

    def avg_fill_price(self):
        """
        Calculate the average fill price of the transaction.

        This is calculated as the total quote quantity divided by the total base quantity.

        Returns:
            float: The average fill price.

        """
        return sum(fill.quote_quantity for fill in self.fills) / sum(
            fill.base_quantity for fill in self.fills
        )
