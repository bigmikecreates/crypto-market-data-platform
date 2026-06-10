from datetime import datetime, timezone
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.providers.base import BasePagedOHLCVProvider
from crmd_platform.providers.http import fetch_json

_BASE_URL = "https://api.gateio.ws/api/v4/spot/candlesticks"

_TIMEFRAME_MAP: dict[str, str] = {
    "10s": "10s",
    "30s": "30s",
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "8h": "8h",
    "1d": "1d",
    "3d": "3d",
    "1w": "7d",
}

_MAX_LIMIT = 1000
_DEFAULT_RATE_LIMIT_SLEEP = 0.1


def _to_gateio_symbol(symbol: str) -> str:
    return symbol.replace("/", "_").upper()


def _to_gateio_timeframe(timeframe: str) -> str:
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
        open=row[5],
        high=row[3],
        low=row[4],
        close=row[2],
        volume=row[1],
        source=source,
    )


class GateioProvider(BasePagedOHLCVProvider):
    _exchange = "gateio"
    _source = "gateio"
    _MAX_LIMIT = _MAX_LIMIT
    _DEFAULT_RATE_LIMIT_SLEEP = _DEFAULT_RATE_LIMIT_SLEEP
    _TIMESTAMP_MULTIPLIER = 1  # Gate.io uses seconds, not milliseconds

    def _provider_symbol(self, symbol: str) -> str:
        return _to_gateio_symbol(symbol)

    def _provider_timeframe(self, timeframe: str) -> str:
        return _to_gateio_timeframe(timeframe)

    def _fetch_page(
        self,
        prov_symbol: str,
        prov_tf: str | int,
        start: int,
        end: int,
    ) -> list[list[str]]:
        url = (
            f"{_BASE_URL}"
            f"?currency_pair={prov_symbol}&interval={prov_tf}"
            f"&from={start}&to={end}&limit={self._MAX_LIMIT}"
        )
        data: Any = fetch_json(url, self._exchange)

        if not isinstance(data, list):
            raise RuntimeError(
                f"Gate.io API error for {prov_symbol}: unexpected response {data}"
            )

        return data

    def _row_timestamp(self, row) -> int:
        return int(row[0])

    def _parse_row(self, row, symbol: str, timeframe: str) -> Candle:
        return _parse_row(row, self._exchange, symbol, timeframe, self._source)
