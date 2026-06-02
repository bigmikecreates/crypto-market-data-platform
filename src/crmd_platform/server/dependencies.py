from fastapi import Request

from crmd_platform.query import QueryService


def get_query_service(request: Request) -> QueryService:
    return request.app.state.query_service


def get_base_path(request: Request) -> str:
    """Return the storage root the server was configured with.

    The path is fixed at startup (via ServerConfig.base_path or --path).
    Per-request path overrides are intentionally removed — callers cannot
    redirect the server to an arbitrary directory or cloud bucket.
    """
    return request.app.state.base_path
