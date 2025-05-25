from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    @abstractmethod
    async def generate_signal(self, market_data: dict) -> dict:
        pass
