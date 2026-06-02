from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://api-pub.bitfinex.com/v2"

_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "3h": "3h",
    "6h": "6h",
    "12h": "12h",
    "1d": "1D",
    "1w": "1W",
    "14d": "14D",
    "1M": "1M",
}

_MAX_LIMIT = 10000
_SORT_ASCENDING = 1
_DEFAULT_RATE_LIMIT_SLEEP = 0.15


def _to_bfx_symbol(symbol: str) -> str:
    if symbol.startswith("t"):
        return symbol
    return f"t{symbol.replace('/', '').upper()}"


def _to_bfx_timeframe(timeframe: str) -> str:
    mapped = _TIMEFRAME_MAP.get(timeframe)
    if mapped is None:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(sorted(_TIMEFRAME_MAP))}"
        )
    return mapped


def _parse_row(
    row: list[Any], exchange: str, symbol: str, timeframe: str, source: str
) -> Candle:
    mts = int(row[0])
    ts = datetime.fromtimestamp(mts / 1000, tz=timezone.utc)
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts.strftime("%Y-%m-%dT%H:%M:%S"),
        open=str(row[1]),
        high=str(row[3]),
        low=str(row[4]),
        close=str(row[2]),
        volume=str(row[5]),
        source=source,
    )


class BitfinexProvider(BasePagedOHLCVProvider):
    _exchange = "bitfinex"
    _source = "bitfinex"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1000

    def _provider_symbol(self, symbol: str) -> str:
        return _to_bfx_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> str:
        return _to_bfx_timeframe(timeframe)

    def _fetch_page(
        self,
        prov_symbol: str,
        prov_tf: str,
        start: int,
        end: int,
    ) -> list[list[Any]]:
        url = (
            f"{_BASE_URL}/candles/trade:{prov_tf}:{prov_symbol}/hist"
            f"?start={start}&end={end}&limit={self._MAX_LIMIT}&sort={_SORT_ASCENDING}"
        )
        data = fetch_json(url, self._exchange)

        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"Bitfinex API error for {prov_symbol}: {data['error']}")

        if not isinstance(data, list):
            return []

        return data

    def _row_timestamp(self, row) -> int:
        return int(row[0])

    def _parse_row(self, row, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
