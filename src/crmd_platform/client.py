from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.providers.base import FundingRateProvider, OHLCVProvider


@dataclass
class FetchResult:
    count: int
    data_type: str
    provider: str
    symbol: str
    timeframe: str | None


class Client(ABC):
    @classmethod
    def local(cls, data_dir: str = "data") -> Client:
        return _LocalClient(data_dir)

    @classmethod
    def remote(cls, base_url: str, api_key: str | None = None) -> Client:
        return _RemoteClient(base_url, api_key)

    @abstractmethod
    def list_datasets(self) -> dict[str, list[str]]: ...

    @abstractmethod
    def get_summary(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def query_candles(
        self,
        exchange: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[Candle]: ...

    @abstractmethod
    def query_funding_rates(
        self,
        exchange: str | None = None,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[FundingRate]: ...

    @abstractmethod
    def query_sql(self, sql: str, limit: int = 100) -> list[dict[str, Any]]: ...

    @abstractmethod
    def fetch_candles(
        self,
        provider: str,
        symbol: str,
        timeframe: str,
        start: datetime | str,
        end: datetime | str | None = None,
    ) -> FetchResult: ...

    @abstractmethod
    def fetch_funding_rates(
        self,
        provider: str,
        symbol: str,
        start: datetime | str,
        end: datetime | str | None = None,
    ) -> FetchResult: ...


class _LocalClient(Client):
    def __init__(self, data_dir: str = "data") -> None:
        try:
            import duckdb  # noqa: F401
        except ImportError:
            raise ImportError(
                "Local mode requires duckdb and pyarrow. "
                "Install: pip install crmd-platform[local]"
            ) from None
        self._data_dir = data_dir

    def list_datasets(self) -> dict[str, list[str]]:
        from crmd_platform.query import DuckDBQueryService

        svc = DuckDBQueryService()
        return svc.list_datasets(base_path=self._data_dir)

    def get_summary(self) -> list[dict[str, Any]]:
        from crmd_platform.query import DuckDBQueryService

        svc = DuckDBQueryService()
        return svc.get_summary(base_path=self._data_dir)

    def query_candles(
        self,
        exchange: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[Candle]:
        from crmd_platform.query import DuckDBQueryService

        svc = DuckDBQueryService()
        return svc.get_candles(
            base_path=self._data_dir,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
            order=order,
        )

    def query_funding_rates(
        self,
        exchange: str | None = None,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[FundingRate]:
        from crmd_platform.query import DuckDBQueryService

        svc = DuckDBQueryService()
        return svc.get_funding_rates(
            base_path=self._data_dir,
            exchange=exchange,
            symbol=symbol,
            start=start,
            end=end,
            limit=limit,
            order=order,
        )

    def query_sql(self, sql: str, limit: int = 100) -> list[dict[str, Any]]:
        from crmd_platform.query import DuckDBQueryService

        svc = DuckDBQueryService()
        rows = svc.raw_sql(sql, base_path=self._data_dir)
        if limit:
            rows = rows[:limit]
        return rows

    def fetch_candles(
        self,
        provider: str,
        symbol: str,
        timeframe: str,
        start: datetime | str,
        end: datetime | str | None = None,
    ) -> FetchResult:
        from crmd_platform.ingestion import OHLCVService
        from crmd_platform.providers import PROVIDERS

        provider_cls = PROVIDERS.get(provider)
        if provider_cls is None:
            available = ", ".join(PROVIDERS)
            raise ValueError(f"Unknown provider '{provider}'. Available: {available}.")

        if not issubclass(provider_cls, OHLCVProvider):
            raise ValueError(
                f"Provider '{provider}' does not support OHLCV data. "
                "Only providers implementing OHLCVProvider are supported."
            )

        if isinstance(start, str):
            start_dt = datetime.strptime(start, "%Y-%m-%d")
        else:
            start_dt = start

        if isinstance(end, str):
            end_dt = datetime.strptime(end, "%Y-%m-%d")
        elif end is None:
            end_dt = datetime.now()
        else:
            end_dt = end

        svc = OHLCVService(provider=provider_cls())
        count = svc.ingest(
            symbol=symbol,
            timeframe=timeframe,
            start=start_dt,
            end=end_dt,
            base_path=self._data_dir,
            merge_strategy="auto",
        )
        return FetchResult(
            count=count,
            data_type="candles",
            provider=provider,
            symbol=symbol,
            timeframe=timeframe,
        )

    def fetch_funding_rates(
        self,
        provider: str,
        symbol: str,
        start: datetime | str,
        end: datetime | str | None = None,
    ) -> FetchResult:
        from crmd_platform.ingestion import FundingRateService
        from crmd_platform.providers import PROVIDERS

        provider_cls = PROVIDERS.get(provider)
        if provider_cls is None:
            available = ", ".join(PROVIDERS)
            raise ValueError(f"Unknown provider '{provider}'. Available: {available}.")

        if not issubclass(provider_cls, FundingRateProvider):
            raise ValueError(
                f"Provider '{provider}' does not support funding rates. "
                "Only providers implementing FundingRateProvider are supported."
            )

        if isinstance(start, str):
            start_dt = datetime.strptime(start, "%Y-%m-%d")
        else:
            start_dt = start

        if isinstance(end, str):
            end_dt = datetime.strptime(end, "%Y-%m-%d")
        elif end is None:
            end_dt = datetime.now()
        else:
            end_dt = end

        svc = FundingRateService(provider=provider_cls())
        count = svc.ingest(
            symbol=symbol,
            start=start_dt,
            end=end_dt,
            base_path=self._data_dir,
            merge_strategy="auto",
        )
        return FetchResult(
            count=count,
            data_type="funding-rates",
            provider=provider,
            symbol=symbol,
            timeframe=None,
        )


class _RemoteClient(Client):
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        import httpx

        self._base_url = base_url.rstrip("/")
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.Client(base_url=self._base_url, headers=headers)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        import httpx

        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.ConnectError:
            raise ConnectionError(
                f"Could not connect to server at {self._base_url}. "
                "Make sure the server is running and reachable."
            )
        except httpx.TimeoutException:
            raise ConnectionError(
                f"Connection to {self._base_url} timed out. "
                "Try again or check your network."
            )
        if resp.status_code == 400:
            detail = resp.json().get("detail", "Bad request")
            raise ValueError(detail)
        if resp.status_code == 401:
            raise PermissionError("Authentication failed. Check your API key.")
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: dict | None = None) -> Any:
        return self._request("POST", path, json=json)

    def list_datasets(self) -> dict[str, list[str]]:
        return self._get("/datasets")

    def get_summary(self) -> list[dict[str, Any]]:
        return self._get("/summary")

    def query_candles(
        self,
        exchange: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[Candle]:
        params = {}
        if exchange:
            params["exchange"] = exchange
        if symbol:
            params["symbol"] = symbol
        if timeframe:
            params["timeframe"] = timeframe
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if limit:
            params["limit"] = str(limit)
        if order:
            params["order"] = order
        data = self._get("/candles", params=params)
        return [Candle(**item) for item in data]

    def query_funding_rates(
        self,
        exchange: str | None = None,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[FundingRate]:
        params = {}
        if exchange:
            params["exchange"] = exchange
        if symbol:
            params["symbol"] = symbol
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if limit:
            params["limit"] = str(limit)
        if order:
            params["order"] = order
        data = self._get("/funding-rates", params=params)
        return [FundingRate(**item) for item in data]

    def query_sql(self, sql: str, limit: int = 100) -> list[dict[str, Any]]:
        data = self._post("/query", json={"sql": sql})
        if limit:
            data = data[:limit]
        return data

    def fetch_candles(
        self,
        provider: str,
        symbol: str,
        timeframe: str,
        start: datetime | str,
        end: datetime | str | None = None,
    ) -> FetchResult:
        body = {
            "data_type": "candles",
            "provider": provider,
            "symbol": symbol,
            "timeframe": timeframe,
            "start": start.isoformat() if isinstance(start, datetime) else start,
        }
        if end is not None:
            body["end"] = end.isoformat() if isinstance(end, datetime) else end
        data = self._post("/fetch", json=body)
        return FetchResult(**data)

    def fetch_funding_rates(
        self,
        provider: str,
        symbol: str,
        start: datetime | str,
        end: datetime | str | None = None,
    ) -> FetchResult:
        body = {
            "data_type": "funding-rates",
            "provider": provider,
            "symbol": symbol,
            "start": start.isoformat() if isinstance(start, datetime) else start,
        }
        if end is not None:
            body["end"] = end.isoformat() if isinstance(end, datetime) else end
        data = self._post("/fetch", json=body)
        return FetchResult(**data)

    def __del__(self) -> None:
        if hasattr(self, "_client"):
            self._client.close()
