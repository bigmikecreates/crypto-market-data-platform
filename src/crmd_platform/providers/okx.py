import time
from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://www.okx.com"

_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "6h": "6H",
    "12h": "12H",
    "1d": "1D",
    "2d": "2D",
    "3d": "3D",
    "1w": "1W",
    "1M": "1M",
    "3M": "3M",
}

_MAX_LIMIT = 300
_DEFAULT_RATE_LIMIT_SLEEP = 0.1


def _to_okx_symbol(symbol: str) -> str:
    return symbol.replace("/", "-").upper()


def _to_okx_timeframe(timeframe: str) -> str:
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


class OkxProvider(BasePagedOHLCVProvider):
    _exchange = "okx"
    _source = "okx"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1000

    def _provider_symbol(self, symbol: str) -> str:
        return _to_okx_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> str:
        return _to_okx_timeframe(timeframe)

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

        all_rows: list[list[str]] = []
        after: int | None = None

        while True:
            rows = self._fetch_page(prov_symbol, prov_tf, after)
            if not rows:
                break

            for row in rows:
                ts = self._row_timestamp(row)
                if ts >= end_ms:
                    continue
                if ts < start_ms:
                    break
                all_rows.append(row)

            oldest_ts = self._row_timestamp(rows[-1])
            if oldest_ts < start_ms or len(rows) < self._MAX_LIMIT:
                break

            after = oldest_ts
            time.sleep(self._rate_limit_sleep)

        all_rows.reverse()
        return [self._parse_row(r, symbol, timeframe) for r in all_rows]

    def _fetch_page(
        self,
        prov_symbol: str,
        prov_tf: str,
        after: int | None = None,
    ) -> list[list[str]]:
        url = (
            f"{_BASE_URL}/api/v5/market/candles"
            f"?instId={prov_symbol}&bar={prov_tf}&limit={self._MAX_LIMIT}"
        )
        if after is not None:
            url += f"&after={after}"

        data: Any = fetch_json(url, self._exchange)
        if not isinstance(data, dict):
            return []
        if data.get("code") != "0":
            raise RuntimeError(
                f"OKX API error for {prov_symbol}: code={data.get('code')} "
                f"msg={data.get('msg', 'unknown')}"
            )
        rows = data.get("data", [])
        if not isinstance(rows, list):
            return []
        return rows

    def _row_timestamp(self, row) -> int:
        return int(row[0])

    def _parse_row(self, row: list[str], symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
