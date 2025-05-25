from typing import ClassVar

from binance.async_client import AsyncClient

from staarb.core.types import Symbol


class BinanceExchangeInfo:
    symbols: ClassVar[dict[str, Symbol]] = {}

    @classmethod
    async def fetch_exchange_info(cls, client: AsyncClient) -> None:
        symbols_info = (await client.get_exchange_info())["symbols"]
        cls.symbols = {symbol["symbol"]: Symbol(**symbol) for symbol in symbols_info}

    @classmethod
    def get_symbol_info(cls, symbol: str) -> Symbol:
        if symbol not in cls.symbols:
            msg = f"Symbol {symbol} not found in exchange info."
            raise ValueError(msg)
        return cls.symbols[symbol]
