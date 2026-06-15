from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://api.huobi.pro"

_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "60min",
    "4h": "4hour",
    "1d": "1day",
    "1w": "1week",
    "1M": "1mon",
}

_MAX_LIMIT = 2000
_DEFAULT_RATE_LIMIT_SLEEP = 0.2


def _to_htx_symbol(symbol: str) -> str:
    return symbol.replace("/", "").lower()


def _to_htx_timeframe(timeframe: str) -> str:
    mapped = _TIMEFRAME_MAP.get(timeframe)
    if mapped is None:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(sorted(_TIMEFRAME_MAP))}"
        )
    return mapped


def _parse_row(
    row: dict, exchange: str, symbol: str, timeframe: str, source: str
) -> Candle:
    ts = datetime.fromtimestamp(int(row["id"]), tz=timezone.utc)
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts.strftime("%Y-%m-%dT%H:%M:%S"),
        open=str(row["open"]),
        high=str(row["high"]),
        low=str(row["low"]),
        close=str(row["close"]),
        volume=str(row["amount"]),
        source=source,
    )


class HtxProvider(BasePagedOHLCVProvider):
    _exchange = "htx"
    _source = "htx"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1

    def _provider_symbol(self, symbol: str) -> str:
        return _to_htx_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> str:
        return _to_htx_timeframe(timeframe)

    def _fetch_page(
        self,
        prov_symbol: str,
        prov_tf: str | int,
        start: int,
        end: int,
    ) -> list[dict]:
        url = (
            f"{_BASE_URL}/market/history/kline"
            f"?symbol={prov_symbol}&period={prov_tf}&size={self._MAX_LIMIT}"
        )
        if start > 0:
            url += f"&from={start}"

        data: Any = fetch_json(url, self._exchange)
        if not isinstance(data, dict):
            return []
        if data.get("status") != "ok":
            raise RuntimeError(
                f"HTX API error for {prov_symbol}: "
                f"status={data.get('status')} "
                f"err-msg={data.get('err-msg', 'unknown')}"
            )
        rows = data.get("data", [])
        if not isinstance(rows, list):
            return []

        rows.reverse()
        return rows

    def _row_timestamp(self, row: dict) -> int:
        return int(row["id"])

    def _parse_row(self, row: dict, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
