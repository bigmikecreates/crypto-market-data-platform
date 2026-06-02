from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://api.bybit.com/v5/market/kline"

_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "6h": "360",
    "12h": "720",
    "1d": "D",
    "1w": "W",
    "1M": "M",
}

_MAX_LIMIT = 1000
_DEFAULT_RATE_LIMIT_SLEEP = 0.2


def _to_bybit_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()


def _to_bybit_timeframe(timeframe: str) -> str:
    mapped = _TIMEFRAME_MAP.get(timeframe)
    if mapped is None:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(sorted(_TIMEFRAME_MAP))}"
        )
    return mapped


def _parse_row(
    row: list[str], exchange: str, symbol: str, timeframe: str, source: str
) -> Candle:
    mts = int(row[0])
    ts = datetime.fromtimestamp(mts / 1000, tz=timezone.utc)
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts.strftime("%Y-%m-%dT%H:%M:%S"),
        open=row[1],
        high=row[2],
        low=row[3],
        close=row[4],
        volume=row[5],
        source=source,
    )


class BybitProvider(BasePagedOHLCVProvider):
    _exchange = "bybit"
    _source = "bybit"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1000

    def _provider_symbol(self, symbol: str) -> str:
        return _to_bybit_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> str:
        return _to_bybit_timeframe(timeframe)

    def _fetch_page(
        self,
        prov_symbol: str,
        prov_tf: str | int,
        start: int,
        end: int,
    ) -> list[list[str]]:
        url = (
            f"{_BASE_URL}"
            f"?category=spot&symbol={prov_symbol}&interval={prov_tf}"
            f"&start={start}&end={end}&limit={self._MAX_LIMIT}"
        )
        data: Any = fetch_json(url, self._exchange)

        if data.get("retCode") != 0:
            raise RuntimeError(
                f"Bybit API error for {prov_symbol}: retCode={data.get('retCode')} "
                f"retMsg={data.get('retMsg', 'unknown')}"
            )

        rows = data.get("result", {}).get("list", [])
        if not isinstance(rows, list):
            return []

        # API returns descending; reverse for ascending pagination
        rows.reverse()
        return rows

    def _row_timestamp(self, row) -> int:
        return int(row[0])

    def _parse_row(self, row, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
