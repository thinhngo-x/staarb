import asyncio
import logging

from binance.async_client import AsyncClient
from binance.exceptions import BinanceOrderMinAmountException, BinanceOrderMinTotalException

from staarb.core.bus.event_bus import EventBus
from staarb.core.bus.events import OrderCreatedEvent, SignalEvent, TransactionClosedEvent
from staarb.core.constants import EPS
from staarb.core.enums import OrderSide, StrategyDecision
from staarb.core.types import Order, Symbol
from staarb.data.exchange_info_fetcher import BinanceExchangeInfo
from staarb.portfolio.position import Position
from staarb.utils import round_step_size

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Portfolio:
    def __init__(
        self,
        name: str,
        client: AsyncClient,
        account_size: float | None = None,
        leverage: float = 3.8,
        quote: str = "USDC",
    ):
        self.name = name
        self.client = client
        self.account_size = account_size
        self._account_updated = asyncio.Event()
        self.quote = quote
        self.leverage = leverage
        self.symbols: set[Symbol] = set()  # Set of symbols in the portfolio
        self.open_positions: dict[Symbol, Position] = {}  # Single open position per symbol
        self.closed_positions: dict[Symbol, list[Position]] = {}  # Closed positions

    async def update_account_size(self, *_):
        """Update the account size from the client."""
        user_assets = (await self.client.get_margin_account())["userAssets"]
        msg = f"User assets fetched: {user_assets}"
        logger.info(msg)
        for asset in user_assets:
            if asset["asset"] == self.quote:
                self.account_size = float(asset["free"])
                break
        msg = (
            f"Account size updated to {self.account_size} {self.quote} "
            f"with leverage {self.leverage} for portfolio {self.name}."
        )
        logger.info(msg)
        self._account_updated.set()
        return self.account_size

    def add_symbol(self, symbol: str | Symbol) -> set[Symbol]:
        """Add a symbol to the portfolio."""
        if isinstance(symbol, str):
            symbol = BinanceExchangeInfo.get_symbol_info(symbol)
        if not isinstance(symbol, Symbol):
            msg = f"Expected symbol to be of type Symbol, got {type(symbol)}."
            raise TypeError(msg)
        if symbol not in self.symbols:
            self.symbols.add(symbol)
        else:
            msg = f"Symbol {symbol} already exists in the portfolio."
            raise ValueError(msg)
        return self.symbols

    async def update_position(self, transaction_closed_event: TransactionClosedEvent):
        """Update the position with a new transaction."""
        transaction = transaction_closed_event.transaction
        symbol = transaction.order.symbol
        if symbol not in self.open_positions:
            self.open_positions[symbol] = Position(symbol=symbol)
        self.open_positions[symbol].update_position(transaction_closed_event)

        # After update, if the position is closed, pop and move it to closed positions
        if self.open_positions[symbol].is_closed:
            position = self.open_positions.pop(symbol)
            if symbol not in self.closed_positions:
                self.closed_positions[symbol] = []
            self.closed_positions[symbol].append(position)

    async def publish_orders(self, signal_event: SignalEvent):
        if signal_event.signal == StrategyDecision.HOLD:
            return  # No orders to publish for HOLD signal
        if signal_event.signal == StrategyDecision.EXIT:
            orders = self._prepare_exit_orders()
        elif signal_event.signal in (StrategyDecision.LONG, StrategyDecision.SHORT):
            orders = await self._prepare_entry_orders(signal_event)
        else:
            msg = f"Invalid signal {signal_event.signal} for portfolio preparation."
            raise ValueError(msg)
        try:
            tasks = [asyncio.create_task(self.filter_order(order)) for order in orders]
            orders = await asyncio.gather(*tasks)
            await EventBus.publish(OrderCreatedEvent, OrderCreatedEvent(orders=orders))
        except (BinanceOrderMinAmountException, BinanceOrderMinTotalException) as e:
            msg = f"Orders are filtered due to: {e}"
            logger.warning(msg)

    async def _prepare_entry_orders(self, signal_event: SignalEvent) -> list[Order]:
        def get_order_side(hedge_ratio: float) -> OrderSide:
            if (hedge_ratio > 0 and signal_event.signal == StrategyDecision.LONG) or (
                hedge_ratio < 0 and signal_event.signal == StrategyDecision.SHORT
            ):
                return OrderSide.BUY
            if (hedge_ratio < 0 and signal_event.signal == StrategyDecision.LONG) or (
                hedge_ratio > 0 and signal_event.signal == StrategyDecision.SHORT
            ):
                return OrderSide.SELL
            msg = f"Invalid hedge ratio {hedge_ratio} for signal {signal_event.signal}."
            raise ValueError(msg)

        agg_position_size = await self.leverage_sizing(signal_event)
        msg = (
            f"Aggregated position size for signal {signal_event.signal} is {agg_position_size} "
            f"with leverage {self.leverage} and account size {self.account_size}."
        )
        logger.info(msg)
        return [
            Order(
                symbol=BinanceExchangeInfo.get_symbol_info(sh.symbol),
                quantity=agg_position_size * abs(sh.hedge_ratio),
                side=get_order_side(sh.hedge_ratio),
            )
            for sh in signal_event.hedge_ratio
        ]

    # TODO: Handle transactions, initiate positions, etc.

    def _prepare_exit_orders(self) -> list[Order]:
        """Prepare exit orders for all positions in the portfolio."""
        orders = []
        for symbol, position in self.open_positions.items():
            if position.size > 0:
                orders.append(
                    Order(
                        symbol=symbol,
                        quantity=position.size,
                        side=OrderSide.SELL,
                    )
                )
            elif position.size < 0:
                orders.append(
                    Order(
                        symbol=symbol,
                        quantity=-position.size,
                        side=OrderSide.BUY,
                    )
                )
        return orders

    async def filter_order(self, order: Order) -> Order:
        """Filter order based on minimum size, etc."""
        if order.symbol not in self.symbols:
            msg = f"Symbol {order.symbol} not found in portfolio."
            raise ValueError(msg)
        symbol = order.symbol
        new_order = Order(
            symbol=order.symbol,
            quantity=round_step_size(order.quantity, symbol.filters.lot_size.step_size),
            side=order.side,
            # Order price can be None for market orders
            price=round_step_size(order.price, symbol.filters.price.tick_size) if order.price else None,
            side_effect=order.side_effect,
            type=order.type,
            time_in_force=order.time_in_force,
        )
        if new_order.quantity < float(symbol.filters.lot_size.min_qty):
            msg = f"Order quantity {new_order.quantity} is below minimum for symbol {order.symbol}."
            raise BinanceOrderMinAmountException(msg)
        avg_price = (
            float((await self.client.get_avg_price(symbol=order.symbol))["price"])
            if not new_order.price
            else new_order.price
        )
        if avg_price * new_order.quantity < float(symbol.filters.notional.min_notional):
            msg = f"Order total {avg_price * new_order.quantity} is below minimum for symbol {order.symbol}."
            raise BinanceOrderMinTotalException(msg)
        return new_order

    async def leverage_sizing(self, signal_event: SignalEvent) -> float:
        """Calculate the size of the order based on the account size and leverage."""
        pos_hedge_weight = sum(
            signal_event.prices[sh.symbol] * sh.hedge_ratio
            for sh in signal_event.hedge_ratio
            if sh.hedge_ratio > 0
        )
        neg_hedge_weight = sum(
            -signal_event.prices[sh.symbol] * sh.hedge_ratio
            for sh in signal_event.hedge_ratio
            if sh.hedge_ratio < 0
        )
        # TODO: Leverage sizing could be even more sophisticated
        await self._account_updated.wait()
        if self.account_size is None:
            msg = (
                "Account size is not set. Please update the account size before calculating leverage sizing."
            )
            raise ValueError(msg)
        leveraged_size = self.account_size * (self.leverage + 1)
        self._account_updated.clear()
        return leveraged_size / (pos_hedge_weight + neg_hedge_weight + EPS)
