from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://api.exchange.coinbase.com"

_GRANULARITY_MAP: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}

_MAX_LIMIT = 300
_DEFAULT_RATE_LIMIT_SLEEP = 0.1


def _to_coinbase_symbol(symbol: str) -> str:
    return symbol.replace("/", "-").upper()


def _to_coinbase_granularity(timeframe: str) -> int:
    g = _GRANULARITY_MAP.get(timeframe)
    if g is None:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(sorted(_GRANULARITY_MAP))}"
        )
    return g


def _parse_row(
    row: list, exchange: str, symbol: str, timeframe: str, source: str
) -> Candle:
    ts = datetime.fromtimestamp(int(row[0]), tz=timezone.utc)
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts.strftime("%Y-%m-%dT%H:%M:%S"),
        open=str(row[3]),
        high=str(row[2]),
        low=str(row[1]),
        close=str(row[4]),
        volume=str(row[5]),
        source=source,
    )


class CoinbaseProvider(BasePagedOHLCVProvider):
    _exchange = "coinbase"
    _source = "coinbase"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1

    def _provider_symbol(self, symbol: str) -> str:
        return _to_coinbase_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> int:
        return _to_coinbase_granularity(timeframe)

    def _fetch_page(
        self, prov_symbol: str, prov_tf: int, start: int, end: int
    ) -> list[list]:
        from_iso = datetime.fromtimestamp(start, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        to_iso = datetime.fromtimestamp(end, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        url = (
            f"{_BASE_URL}/products/{prov_symbol}/candles"
            f"?granularity={prov_tf}"
            f"&start={from_iso}&end={to_iso}"
        )
        data: Any = fetch_json(url, self._exchange)
        if not isinstance(data, list):
            raise RuntimeError(
                f"Coinbase API error for {prov_symbol}: "
                f"unexpected response {data}"
            )
        return data

    def _row_timestamp(self, row: list) -> int:
        return int(row[0])

    def _parse_row(self, row: list, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
