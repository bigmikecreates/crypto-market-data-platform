from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from crypto_market_data_platform.server.config import ServerConfig
from crypto_market_data_platform.server.routers import (
    health,
    datasets,
    candles,
    funding,
    query,
    summary,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(config: ServerConfig | None = None) -> FastAPI:
    if config is None:
        config = ServerConfig()

    app = FastAPI(title="cmpd", version="0.1.0", lifespan=lifespan)

    app.state.query_service = config.query_service
    app.state.base_path = config.base_path

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def handle_exception(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "code": 500},
        )

    app.include_router(health.router)
    app.include_router(datasets.router)
    app.include_router(candles.router)
    app.include_router(funding.router)
    app.include_router(query.router)
    app.include_router(summary.router)

    return app
