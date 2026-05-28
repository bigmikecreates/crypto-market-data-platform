import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.base import OHLCVProvider

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
_RATE_LIMIT_SLEEP = 0.05


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


class MexcProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = _RATE_LIMIT_SLEEP) -> None:
        self._exchange = "mexc"
        self._source = "mexc"
        self._rate_limit_sleep = rate_limit_sleep

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        mexc_symbol = _to_mexc_symbol(symbol)
        mexc_tf = _to_mexc_timeframe(timeframe)

        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        candles: list[Candle] = []
        current_start = start_ms

        while current_start < end_ms:
            rows = self._fetch_ohlcv_page(mexc_symbol, mexc_tf, current_start, end_ms)
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
        mexc_symbol: str,
        mexc_timeframe: str,
        start_ms: int,
        end_ms: int,
    ) -> list[list[str]]:
        url = (
            f"{_BASE_URL}"
            f"?symbol={mexc_symbol}&interval={mexc_timeframe}"
            f"&startTime={start_ms}&endTime={end_ms}&limit={_MAX_LIMIT}"
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
                data: Any = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                err_info = json.loads(body)
            except json.JSONDecodeError:
                err_info = body
            raise RuntimeError(
                f"MEXC API error for {mexc_symbol}: {err_info}"
            ) from None

        if not isinstance(data, list):
            raise RuntimeError(
                f"MEXC API error for {mexc_symbol}: unexpected response {data}"
            )

        return data
