import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from crmd_platform.server.config import ServerConfig
from crmd_platform.server.routers import (
    health,
    datasets,
    candles,
    funding,
    query,
    summary,
)

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(config: ServerConfig | None = None) -> FastAPI:
    if config is None:
        config = ServerConfig()

    app = FastAPI(title="CrMD Platform", version="0.1.0", lifespan=lifespan)

    app.state.query_service = config.query_service
    app.state.base_path = config.base_path
    app.state.api_key = config.api_key

    if config.api_key is None:
        _log.warning(
            "CRMD_API_KEY is not set — server is running in open dev mode. "
            "Set api_key in ServerConfig or pass --api-key to crmd serve before exposing this port."
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "X-API-Key", "Content-Type"],
    )

    from crmd_platform.server.auth import require_api_key
    from fastapi import Depends

    _auth = [Depends(require_api_key)]

    @app.exception_handler(Exception)
    async def handle_exception(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, (SystemExit, KeyboardInterrupt, GeneratorExit)):
            raise exc
        _log.error("Unhandled exception on %s %s", request.method, request.url, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": "An internal server error occurred.", "code": 500},
        )

    # /health is exempt — load-balancers probe it without credentials.
    app.include_router(health.router)
    app.include_router(datasets.router, dependencies=_auth)
    app.include_router(candles.router, dependencies=_auth)
    app.include_router(funding.router, dependencies=_auth)
    app.include_router(query.router, dependencies=_auth)
    app.include_router(summary.router, dependencies=_auth)

    return app
