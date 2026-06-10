from dataclasses import dataclass, field

from crmd_platform.query import DuckDBQueryService, QueryService
from crmd_platform.storage.backend import StorageBackend


@dataclass(slots=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8050
    base_path: str = "data"
    query_service: QueryService = field(default_factory=DuckDBQueryService)
    # Optional storage backend. If None, created from base_path.
    storage_backend: StorageBackend | None = None
    # None = dev mode (open access). Set via CRMD_API_KEY env var or --api-key CLI flag.
    api_key: str | None = None
    # Restrict CORS to specific origins. Defaults to localhost frontends only.
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
