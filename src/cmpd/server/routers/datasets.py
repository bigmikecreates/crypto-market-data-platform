from fastapi import APIRouter, Depends, Query

from cmpd.query import QueryService
from cmpd.server.dependencies import get_query_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
async def list_datasets(
    path: str = Query(default="data"),
    qs: QueryService = Depends(get_query_service),
):
    return qs.list_datasets(base_path=path)
