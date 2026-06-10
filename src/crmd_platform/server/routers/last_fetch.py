from fastapi import APIRouter, Depends

from crmd_platform.server.dependencies import get_base_path
from crmd_platform.utils.last_fetch import read as read_last_fetch

router = APIRouter(tags=["last-fetch"])


@router.get("/last-fetch")
async def last_fetch(base_path: str = Depends(get_base_path)):
    ts = read_last_fetch(base_path)
    return {"timestamp": ts}
