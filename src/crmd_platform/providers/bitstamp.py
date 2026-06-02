from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://www.bitstamp.net/api/v2/ohlc"

_STEP_MAP: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
    "3d": 259200,
}

_MAX_LIMIT = 1000
_DEFAULT_RATE_LIMIT_SLEEP = 0.05


def _to_bitstamp_symbol(symbol: str) -> str:
    return symbol.replace("/", "").lower()


def _to_bitstamp_timeframe(timeframe: str) -> int:
    step = _STEP_MAP.get(timeframe)
    if step is None:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(sorted(_STEP_MAP))}"
        )
    return step


def _parse_row(
    row: dict[str, str], exchange: str, symbol: str, timeframe: str, source: str
) -> Candle:
    ts = datetime.fromtimestamp(int(row["timestamp"]), tz=timezone.utc)
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts.strftime("%Y-%m-%dT%H:%M:%S"),
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        volume=row["volume"],
        source=source,
    )


class BitstampProvider(BasePagedOHLCVProvider):
    _exchange = "bitstamp"
    _source = "bitstamp"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1

    def _provider_symbol(self, symbol: str) -> str:
        return _to_bitstamp_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> int:
        return _to_bitstamp_timeframe(timeframe)

    def _fetch_page(
        self,
        prov_symbol: str,
        prov_tf: int,
        start: int,
        end: int,
    ) -> list[dict[str, str]]:
        url = (
            f"{_BASE_URL}/{prov_symbol}/"
            f"?step={prov_tf}&limit={self._MAX_LIMIT}"
            f"&start={start}&end={end}"
        )
        data: Any = fetch_json(url, self._exchange)

        ohlc_data = data.get("data", {})
        if not isinstance(ohlc_data, dict):
            return []
        rows = ohlc_data.get("ohlc", [])
        if not isinstance(rows, list):
            return []
        return rows

    def _row_timestamp(self, row) -> int:
        return int(row["timestamp"])

    def _parse_row(self, row, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
