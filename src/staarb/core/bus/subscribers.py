from staarb.core.bus.event_bus import EventBus
from staarb.core.bus.events import (
    MarketDataEvent,
    OrderCreatedEvent,
    PositionEvent,
    SignalEvent,
    TransactionClosedEvent,
)
from staarb.persistence.storage import TradingStorage
from staarb.portfolio import Portfolio
from staarb.strategy.statistical_arbitrage import StatisticalArbitrage
from staarb.trader.order_executor import OrderExecutor


def setup_backtest_subscribers(
    strategy: StatisticalArbitrage,
    portfolio: Portfolio,
    executor: OrderExecutor,
    storage: TradingStorage | None = None,
):
    EventBus.subscribe(MarketDataEvent, strategy.on_market_data)
    EventBus.subscribe(MarketDataEvent, portfolio.update_account_size)
    EventBus.subscribe(SignalEvent, portfolio.publish_orders)
    EventBus.subscribe(OrderCreatedEvent, executor.execute_order)
    EventBus.subscribe(TransactionClosedEvent, portfolio.update_position)
    EventBus.subscribe(TransactionClosedEvent, strategy.update_position)
    EventBus.subscribe(PositionEvent, storage.save_position) if storage else None
