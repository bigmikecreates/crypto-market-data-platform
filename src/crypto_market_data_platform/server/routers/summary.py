from fastapi import APIRouter, Depends, Query

from crypto_market_data_platform.query import QueryService
from crypto_market_data_platform.server.dependencies import get_query_service

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("")
async def get_summary(
    path: str = Query(default="data"),
    qs: QueryService = Depends(get_query_service),
):
    return qs.get_summary(base_path=path)
