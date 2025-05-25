from asyncio import create_task, gather

import pandas as pd
from binance.async_client import AsyncClient

from staarb.core.types import KLINE_COLUMNS, DataRequest, LookbackRequest


class MarketDataFetcher:
    """
    MarketDataFetcher is a class that fetches market data from the Binance API.
    """

    @classmethod
    async def fetch_klines(cls, client: AsyncClient, symbol: str, request: DataRequest | LookbackRequest):
        """
        Fetch klines (candlestick data) for a given symbol and request parameters.
        """
        if isinstance(request, DataRequest):
            klines = await client.get_historical_klines(
                symbol,
                request.interval,
                start_str=request.start,
                end_str=request.end,
            )
        elif isinstance(request, LookbackRequest):
            klines = await client.get_historical_klines(
                symbol,
                request.interval,
                limit=request.limit,
            )
        else:
            msg = f"Invalid request type: {type(request)}"
            raise TypeError(msg)
        klines = pd.DataFrame(klines, columns=KLINE_COLUMNS, dtype=float)
        klines["open_time"] = pd.to_datetime(klines["open_time"], unit="ms")

        return klines.set_index("open_time")[request.columns]

    @classmethod
    async def fetch_multiple_klines(
        cls, client: AsyncClient, symbols: list[str], request: DataRequest | LookbackRequest
    ):
        """
        Fetch klines (candlestick data) for the given list of symbols and request parameters.
        """
        tasks = [create_task(cls.fetch_klines(client, symbol, request)) for symbol in symbols]
        results = await gather(*tasks)
        return dict(zip(symbols, results, strict=False))
