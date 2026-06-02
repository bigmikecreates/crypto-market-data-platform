from fastapi import APIRouter, Depends

from crmd_platform.query import QueryService
from crmd_platform.server.dependencies import get_base_path, get_query_service

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("")
async def get_summary(
    base_path: str = Depends(get_base_path),
    qs: QueryService = Depends(get_query_service),
):
    return qs.get_summary(base_path=base_path)
