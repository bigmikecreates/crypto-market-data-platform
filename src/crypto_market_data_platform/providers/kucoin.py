import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.base import MarketDataProvider

_BASE_URL = "https://api.kucoin.com/api/v1/market/candles"

_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1hour",
    "2h": "2hour",
    "4h": "4hour",
    "6h": "6hour",
    "8h": "8hour",
    "12h": "12hour",
    "1d": "1day",
    "1w": "1week",
}

_MAX_LIMIT = 1500
_RATE_LIMIT_SLEEP = 0.1


def _to_kc_symbol(symbol: str) -> str:
    if "-" in symbol:
        return symbol.upper()
    return symbol.replace("/", "-").upper()


def _to_kc_timeframe(timeframe: str) -> str:
    mapped = _TIMEFRAME_MAP.get(timeframe)
    if mapped is None:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(sorted(_TIMEFRAME_MAP))}"
        )
    return mapped


def _parse_row(row: list[str], exchange: str, symbol: str, timeframe: str, source: str) -> Candle:
    ts = datetime.fromtimestamp(int(row[0]), tz=timezone.utc)
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts.strftime("%Y-%m-%dT%H:%M:%S"),
        open=row[1],
        high=row[3],
        low=row[4],
        close=row[2],
        volume=row[5],
        source=source,
    )


class KuCoinProvider(MarketDataProvider):
    def __init__(self, rate_limit_sleep: float = _RATE_LIMIT_SLEEP) -> None:
        self._exchange = "kucoin"
        self._source = "kucoin"
        self._rate_limit_sleep = rate_limit_sleep

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        kc_symbol = _to_kc_symbol(symbol)
        kc_tf = _to_kc_timeframe(timeframe)

        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())

        candles: list[Candle] = []
        current_start = start_ts

        while current_start < end_ts:
            rows = self._fetch_ohlcv_page(kc_symbol, kc_tf, current_start, end_ts)
            if not rows:
                break

            for row in rows:
                candle_ts = int(row[0])
                if candle_ts < start_ts or candle_ts >= end_ts:
                    continue
                c = _parse_row(row, self._exchange, symbol, timeframe, self._source)
                candles.append(c)

            last_ts = int(rows[-1][0])
            if len(rows) < _MAX_LIMIT:
                break
            current_start = last_ts + 1
            time.sleep(self._rate_limit_sleep)

        return candles

    def _fetch_ohlcv_page(
        self,
        kc_symbol: str,
        kc_timeframe: str,
        start_ts: int,
        end_ts: int,
    ) -> list[list[str]]:
        url = (
            f"{_BASE_URL}"
            f"?symbol={kc_symbol}&type={kc_timeframe}"
            f"&startAt={start_ts}&endAt={end_ts}"
        )
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) crypto-market-data-platform/1.0",
        })
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
                f"KuCoin API error for {kc_symbol}: {err_info}"
            ) from None

        if data.get("code") != "200000":
            raise RuntimeError(
                f"KuCoin API error for {kc_symbol}: code={data.get('code')} "
                f"msg={data.get('msg', 'unknown')}"
            )

        rows = data.get("data", [])
        if not isinstance(rows, list):
            return []
        return rows
