from dataclasses import dataclass, field

from cmpd.query import DuckDBQueryService, QueryService


@dataclass(slots=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    base_path: str = "data"
    query_service: QueryService = field(default_factory=DuckDBQueryService)
