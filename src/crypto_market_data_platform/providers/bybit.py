import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.base import OHLCVProvider

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
_RATE_LIMIT_SLEEP = 0.2


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


def _parse_row(row: list[str], exchange: str, symbol: str, timeframe: str, source: str) -> Candle:
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


class BybitProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = _RATE_LIMIT_SLEEP) -> None:
        self._exchange = "bybit"
        self._source = "bybit"
        self._rate_limit_sleep = rate_limit_sleep

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        bybit_symbol = _to_bybit_symbol(symbol)
        bybit_tf = _to_bybit_timeframe(timeframe)

        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        candles: list[Candle] = []
        current_start = start_ms

        while current_start < end_ms:
            rows = self._fetch_ohlcv_page(
                bybit_symbol, bybit_tf, current_start, end_ms
            )
            if not rows:
                break

            rows.reverse()

            for row in rows:
                mts = int(row[0])
                if mts < start_ms or mts >= end_ms:
                    continue
                c = _parse_row(row, self._exchange, symbol, timeframe, self._source)
                candles.append(c)

            last_mts = int(rows[-1][0])
            if len(rows) < _MAX_LIMIT:
                break
            current_start = last_mts + 1
            time.sleep(self._rate_limit_sleep)

        return candles

    def _fetch_ohlcv_page(
        self,
        bybit_symbol: str,
        bybit_timeframe: str,
        start_ms: int,
        end_ms: int,
    ) -> list[list[str]]:
        url = (
            f"{_BASE_URL}"
            f"?category=spot&symbol={bybit_symbol}&interval={bybit_timeframe}"
            f"&start={start_ms}&end={end_ms}&limit={_MAX_LIMIT}"
        )
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) crypto-market-data-platform/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data: Any = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                err_info = json.loads(body)
            except json.JSONDecodeError:
                err_info = body
            raise RuntimeError(
                f"Bybit API error for {bybit_symbol}: {err_info}"
            ) from None

        if data.get("retCode") != 0:
            raise RuntimeError(
                f"Bybit API error for {bybit_symbol}: retCode={data.get('retCode')} "
                f"retMsg={data.get('retMsg', 'unknown')}"
            )

        rows = data.get("result", {}).get("list", [])
        if not isinstance(rows, list):
            return []
        return rows
