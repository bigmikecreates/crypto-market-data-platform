import time
from abc import ABC, abstractmethod
from datetime import datetime

from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate


class OHLCVProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]: ...


class FundingRateProvider(ABC):
    @abstractmethod
    def fetch_funding_rates(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[FundingRate]: ...


def fetch_paginated_ohlcv(
    provider: "BasePagedOHLCVProvider",
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> list[Candle]:
    """Run the common pagination loop for a provider that implements the paged interface."""
    mult = provider._TIMESTAMP_MULTIPLIER  # type: ignore[attr-defined]
    start_ts = int(start.timestamp()) * mult
    end_ts = int(end.timestamp()) * mult
    prov_symbol = provider._provider_symbol(symbol)
    prov_tf = provider._provider_timeframe(timeframe)
    candles: list[Candle] = []
    current_start = start_ts
    while current_start < end_ts:
        rows = provider._fetch_page(prov_symbol, prov_tf, current_start, end_ts)
        if not rows:
            break
        for row in rows:
            ts = provider._row_timestamp(row)
            if ts < start_ts or ts >= end_ts:
                continue
            candles.append(provider._parse_row(row, symbol, timeframe))
        if len(rows) < provider._MAX_LIMIT:
            break
        current_start = provider._advance_cursor(rows)
        time.sleep(provider._rate_limit_sleep)
    return candles


class BasePagedOHLCVProvider(OHLCVProvider):
    """OHLCV provider with a template-method pagination loop.

    Subclasses must set class-level constants and implement the abstract hooks.
    The module-level module functions (e.g. _parse_row, _to_*_symbol) are kept
    for backward compatibility with direct imports in tests and smoke scripts.
    """

    _exchange: str
    _source: str
    _rate_limit_sleep: float
    _MAX_LIMIT: int = 1000
    _TIMESTAMP_MULTIPLIER: int = 1000
    _DEFAULT_RATE_LIMIT_SLEEP: float = 1.0

    def __init__(self, rate_limit_sleep: float | None = None) -> None:
        self._rate_limit_sleep = (
            rate_limit_sleep
            if rate_limit_sleep is not None
            else self._DEFAULT_RATE_LIMIT_SLEEP
        )

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        return fetch_paginated_ohlcv(self, symbol, timeframe, start, end)

    @abstractmethod
    def _provider_symbol(self, symbol: str) -> str: ...

    @abstractmethod
    def _provider_timeframe(self, timeframe: str) -> str | int: ...

    @abstractmethod
    def _fetch_page(
        self, prov_symbol: str, prov_tf: str | int, start: int, end: int
    ) -> list: ...

    @abstractmethod
    def _row_timestamp(self, row) -> int: ...

    @abstractmethod
    def _parse_row(self, row, symbol: str, timeframe: str) -> Candle: ...

    def _advance_cursor(self, rows) -> int:
        return self._row_timestamp(rows[-1]) + 1
