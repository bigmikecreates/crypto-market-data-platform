from datetime import datetime, timezone

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

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
_DEFAULT_RATE_LIMIT_SLEEP = 0.1


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


def _parse_row(
    row: list[str], exchange: str, symbol: str, timeframe: str, source: str
) -> Candle:
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


class KuCoinProvider(BasePagedOHLCVProvider):
    _exchange = "kucoin"
    _source = "kucoin"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1

    def _provider_symbol(self, symbol: str) -> str:
        return _to_kc_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> str:
        return _to_kc_timeframe(timeframe)

    def _fetch_page(
        self,
        prov_symbol: str,
        prov_tf: str,
        start: int,
        end: int,
    ) -> list[list[str]]:
        url = (
            f"{_BASE_URL}"
            f"?symbol={prov_symbol}&type={prov_tf}"
            f"&startAt={start}&endAt={end}"
        )
        data = fetch_json(url, self._exchange)

        if data.get("code") != "200000":
            raise RuntimeError(
                f"KuCoin API error for {prov_symbol}: code={data.get('code')} "
                f"msg={data.get('msg', 'unknown')}"
            )

        rows = data.get("data", [])
        if not isinstance(rows, list):
            return []

        return rows

    def _row_timestamp(self, row) -> int:
        return int(row[0])

    def _parse_row(self, row, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
