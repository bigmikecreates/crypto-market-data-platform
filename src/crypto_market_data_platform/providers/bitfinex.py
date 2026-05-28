import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.base import OHLCVProvider

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

_RATE_LIMIT_SLEEP = 0.15


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


class BitfinexProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = _RATE_LIMIT_SLEEP) -> None:
        self._exchange = "bitfinex"
        self._source = "bitfinex"
        self._rate_limit_sleep = rate_limit_sleep

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        bfx_symbol = _to_bfx_symbol(symbol)
        bfx_tf = _to_bfx_timeframe(timeframe)

        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        candles: list[Candle] = []
        current_start = start_ms

        while current_start < end_ms:
            rows = self._fetch_ohlcv_page(bfx_symbol, bfx_tf, current_start, end_ms)
            if not rows:
                break

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
        bfx_symbol: str,
        bfx_timeframe: str,
        start_ms: int,
        end_ms: int,
    ) -> list[list[Any]]:
        url = (
            f"{_BASE_URL}/candles/trade:{bfx_timeframe}:{bfx_symbol}/hist"
            f"?start={start_ms}&end={end_ms}&limit={_MAX_LIMIT}&sort={_SORT_ASCENDING}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) crypto-market-data-platform/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                err_info = json.loads(body)
            except json.JSONDecodeError:
                err_info = body
            raise RuntimeError(
                f"Bitfinex API error for {bfx_symbol}: {err_info}"
            ) from None

        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"Bitfinex API error for {bfx_symbol}: {data['error']}")

        if not isinstance(data, list):
            return []

        return data
