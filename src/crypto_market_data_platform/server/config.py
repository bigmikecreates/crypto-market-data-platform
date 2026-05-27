from dataclasses import dataclass, field

from crypto_market_data_platform.query import DuckDBQueryService, QueryService


@dataclass(slots=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    base_path: str = "data"
    query_service: QueryService = field(default_factory=DuckDBQueryService)
