from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://api.mexc.com/api/v3/klines"

_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "4h",
    "1d": "1d",
    "1w": "1W",
    "1M": "1M",
}

_MAX_LIMIT = 500
_DEFAULT_RATE_LIMIT_SLEEP = 0.05


def _to_mexc_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()


def _to_mexc_timeframe(timeframe: str) -> str:
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


class MexcProvider(BasePagedOHLCVProvider):
    _exchange = "mexc"
    _source = "mexc"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1000

    def _provider_symbol(self, symbol: str) -> str:
        return _to_mexc_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> str:
        return _to_mexc_timeframe(timeframe)

    def _fetch_page(
        self,
        prov_symbol: str,
        prov_tf: str,
        start: int,
        end: int,
    ) -> list[list[str]]:
        url = (
            f"{_BASE_URL}"
            f"?symbol={prov_symbol}&interval={prov_tf}"
            f"&startTime={start}&endTime={end}&limit={self._MAX_LIMIT}"
        )
        data: Any = fetch_json(url, self._exchange)

        if not isinstance(data, list):
            raise RuntimeError(
                f"MEXC API error for {prov_symbol}: unexpected response {data}"
            )

        return data

    def _row_timestamp(self, row) -> int:
        return int(row[0])

    def _parse_row(self, row, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
