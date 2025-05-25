import logging
from asyncio import create_task, gather
from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from staarb.core.bus.events import BaseEvent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventBus:
    """
    EventBus is a simple event bus implementation that allows for the registration of event handlers
    and the publishing of events to those handlers.
    """

    _handlers: ClassVar[dict[type["BaseEvent"], list[Callable]]] = {}

    @classmethod
    def subscribe(cls, event_type: type["BaseEvent"], handler: Callable) -> None:
        """
        Subscribe a handler to an event type.

        The handler will be called with the event data when the event is published.
        """
        if event_type not in cls._handlers:
            cls._handlers[event_type] = []
        cls._handlers[event_type].append(handler)

    @classmethod
    async def publish(cls, event_type: type["BaseEvent"], data=None) -> None:
        """
        Publish an event to all registered handlers for that event type.
        """
        if event_type in cls._handlers:
            msg = f"Publishing event {event_type.__name__} with data: {data}"
            logger.info(msg)
            tasks = [create_task(handler(data)) for handler in cls._handlers[event_type]]
            await gather(*tasks)
