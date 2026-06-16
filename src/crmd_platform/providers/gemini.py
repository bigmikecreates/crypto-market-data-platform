from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://api.gemini.com"

_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "6h": "6h",
    "1d": "1d",
}

_DEFAULT_RATE_LIMIT_SLEEP = 0.5


def _to_gemini_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()


def _to_gemini_timeframe(timeframe: str) -> str:
    mapped = _TIMEFRAME_MAP.get(timeframe)
    if mapped is None:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(sorted(_TIMEFRAME_MAP))}"
        )
    return mapped


def _parse_row(
    row: list, exchange: str, symbol: str, timeframe: str, source: str
) -> Candle:
    mts = int(row[0])
    ts = datetime.fromtimestamp(mts / 1000, tz=timezone.utc)
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts.strftime("%Y-%m-%dT%H:%M:%S"),
        open=str(row[1]),
        high=str(row[2]),
        low=str(row[3]),
        close=str(row[4]),
        volume=str(row[5]),
        source=source,
    )


class GeminiProvider(BasePagedOHLCVProvider):
    _exchange = "gemini"
    _source = "gemini"
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1000

    def _provider_symbol(self, symbol: str) -> str:
        return _to_gemini_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> str:
        return _to_gemini_timeframe(timeframe)

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        mult = self._TIMESTAMP_MULTIPLIER
        start_ms = int(start.timestamp()) * mult
        end_ms = int(end.timestamp()) * mult
        prov_symbol = self._provider_symbol(symbol)
        prov_tf = self._provider_timeframe(timeframe)

        rows = self._fetch_page(prov_symbol, prov_tf)

        candles: list[Candle] = []
        for row in rows:
            ts = self._row_timestamp(row)
            if start_ms <= ts < end_ms:
                candles.append(self._parse_row(row, symbol, timeframe))

        return candles

    def _fetch_page(  # type: ignore[override]
        self,
        prov_symbol: str,
        prov_tf: str,
        start: int = 0,
        end: int = 0,
    ) -> list[list]:
        url = f"{_BASE_URL}/v2/candles/{prov_symbol}/{prov_tf}"
        data: Any = fetch_json(url, self._exchange)
        if not isinstance(data, list):
            return []
        return data

    def _row_timestamp(self, row) -> int:
        return int(row[0])

    def _parse_row(self, row: list, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
