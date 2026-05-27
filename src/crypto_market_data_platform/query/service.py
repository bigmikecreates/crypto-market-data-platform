from abc import ABC, abstractmethod
from typing import Any

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate


class QueryService(ABC):
    @abstractmethod
    def list_datasets(
        self, base_path: str = "data"
    ) -> dict[str, list[str]]:
        ...

    @abstractmethod
    def get_candles(
        self,
        base_path: str = "data",
        exchange: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[Candle]:
        ...

    @abstractmethod
    def get_funding_rates(
        self,
        base_path: str = "data",
        exchange: str | None = None,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[FundingRate]:
        ...

    @abstractmethod
    def get_summary(
        self, base_path: str = "data"
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def raw_sql(
        self, sql: str, base_path: str = "data"
    ) -> list[dict[str, Any]]:
        ...
