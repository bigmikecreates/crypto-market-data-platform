from fastapi import APIRouter, Depends

from crmd_platform.query import QueryService
from crmd_platform.server.dependencies import get_base_path, get_query_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
async def list_datasets(
    base_path: str = Depends(get_base_path),
    qs: QueryService = Depends(get_query_service),
):
    return qs.list_datasets(base_path=base_path)
