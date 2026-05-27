from pydantic import BaseModel

from fastapi import APIRouter, Depends

from crypto_market_data_platform.query import QueryService
from crypto_market_data_platform.server.dependencies import get_query_service

router = APIRouter(prefix="/query", tags=["query"])


class SqlBody(BaseModel):
    sql: str
    path: str = "data"


@router.post("")
async def raw_query(
    body: SqlBody,
    qs: QueryService = Depends(get_query_service),
):
    return qs.raw_sql(sql=body.sql, base_path=body.path)
