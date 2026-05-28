import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.base import OHLCVProvider

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
_RATE_LIMIT_SLEEP = 0.05


def _to_bitstamp_symbol(symbol: str) -> str:
    return symbol.replace("/", "").lower()


def _to_bitstamp_step(timeframe: str) -> int:
    step = _STEP_MAP.get(timeframe)
    if step is None:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(sorted(_STEP_MAP))}"
        )
    return step


def _parse_row(row: dict[str, str], exchange: str, symbol: str, timeframe: str, source: str) -> Candle:
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


class BitstampProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = _RATE_LIMIT_SLEEP) -> None:
        self._exchange = "bitstamp"
        self._source = "bitstamp"
        self._rate_limit_sleep = rate_limit_sleep

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        bs_symbol = _to_bitstamp_symbol(symbol)
        step = _to_bitstamp_step(timeframe)

        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())

        candles: list[Candle] = []
        current_start = start_ts

        while current_start < end_ts:
            rows = self._fetch_ohlcv_page(bs_symbol, step, current_start, end_ts)
            if not rows:
                break

            for row in rows:
                ts = int(row["timestamp"])
                if ts < start_ts or ts >= end_ts:
                    continue
                c = _parse_row(row, self._exchange, symbol, timeframe, self._source)
                candles.append(c)

            last_ts = int(rows[-1]["timestamp"])
            if len(rows) < _MAX_LIMIT:
                break
            current_start = last_ts + 1
            time.sleep(self._rate_limit_sleep)

        return candles

    def _fetch_ohlcv_page(
        self,
        bs_symbol: str,
        step: int,
        start_ts: int,
        end_ts: int,
    ) -> list[dict[str, str]]:
        url = (
            f"{_BASE_URL}/{bs_symbol}/"
            f"?step={step}&limit={_MAX_LIMIT}"
            f"&start={start_ts}&end={end_ts}"
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
                f"Bitstamp API error for {bs_symbol}: {err_info}"
            ) from None

        ohlc_data = data.get("data", {})
        if not isinstance(ohlc_data, dict):
            return []
        rows = ohlc_data.get("ohlc", [])
        if not isinstance(rows, list):
            return []
        return rows
