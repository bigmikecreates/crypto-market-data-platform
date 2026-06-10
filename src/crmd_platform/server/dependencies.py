from fastapi import Request

from crmd_platform.query import QueryService
from crmd_platform.storage.backend import StorageBackend, create_backend


def get_query_service(request: Request) -> QueryService:
    return request.app.state.query_service


def get_base_path(request: Request) -> str:
    """Return the storage root the server was configured with.

    The path is fixed at startup (via ServerConfig.base_path or --path).
    Per-request path overrides are intentionally removed — callers cannot
    redirect the server to an arbitrary directory or cloud bucket.
    """
    return request.app.state.base_path


def get_storage_backend(request: Request) -> StorageBackend:
    """Return the storage backend the server was configured with.

    If no explicit backend was provided, creates one from base_path.
    The backend is cached on the app state for reuse across requests.
    """
    backend = getattr(request.app.state, "storage_backend", None)
    if backend is None:
        backend = create_backend(request.app.state.base_path)
        request.app.state.storage_backend = backend
    return backend
