from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://api.kraken.com"

_INTERVAL_MAP: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}

_MAX_LIMIT = 720
_DEFAULT_RATE_LIMIT_SLEEP = 1.0


def _to_kraken_symbol(symbol: str) -> str:
    s = symbol.replace("/", "").upper()
    return s.replace("BTC", "XBT")


def _to_kraken_interval(timeframe: str) -> int:
    mapped = _INTERVAL_MAP.get(timeframe)
    if mapped is None:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(sorted(_INTERVAL_MAP))}"
        )
    return mapped


def _parse_row(
    row: list[str | int], exchange: str, symbol: str, timeframe: str, source: str
) -> Candle:
    ts = datetime.fromtimestamp(int(row[0]), tz=timezone.utc)
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts.strftime("%Y-%m-%dT%H:%M:%S"),
        open=str(row[1]),
        high=str(row[2]),
        low=str(row[3]),
        close=str(row[4]),
        volume=str(row[6]),
        source=source,
    )


class KrakenProvider(BasePagedOHLCVProvider):
    _exchange = "kraken"
    _source = "kraken"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1

    def _provider_symbol(self, symbol: str) -> str:
        return _to_kraken_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> int:
        return _to_kraken_interval(timeframe)

    def _fetch_page(
        self,
        prov_symbol: str,
        prov_tf: str | int,
        start: int,
        end: int,
    ) -> list[list]:
        url = (
            f"{_BASE_URL}/0/public/OHLC"
            f"?pair={prov_symbol}&interval={prov_tf}"
        )
        if start > 0:
            url += f"&since={start}"

        data: Any = fetch_json(url, self._exchange)
        if not isinstance(data, dict):
            return []
        errs = data.get("error", [])
        if errs:
            raise RuntimeError(
                f"Kraken API error for {prov_symbol}: {', '.join(errs)}"
            )
        result = data.get("result", {})
        if not isinstance(result, dict):
            return []
        rows: list[list] = []
        for key, value in result.items():
            if key != "last":
                if isinstance(value, list):
                    rows = value
                break
        return rows

    def _row_timestamp(self, row) -> int:
        return int(row[0])

    def _parse_row(self, row: list, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
