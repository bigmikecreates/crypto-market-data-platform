from typing import Literal

from fastapi import APIRouter, Depends, Query

from crmd_platform.query import QueryService
from crmd_platform.server.dependencies import get_base_path, get_query_service

router = APIRouter(prefix="/candles", tags=["candles"])


@router.get("")
async def get_candles(
    base_path: str = Depends(get_base_path),
    exchange: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=10000),
    order: Literal["DESC", "ASC"] = Query(default="DESC"),
    qs: QueryService = Depends(get_query_service),
):
    return qs.get_candles(
        base_path=base_path,
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
        order=order,
    )
