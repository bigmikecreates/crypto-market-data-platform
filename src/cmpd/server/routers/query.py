import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cmpd.query import QueryService
from cmpd.server.dependencies import get_query_service

router = APIRouter(prefix="/query", tags=["query"])

# Matches the first SQL keyword after stripping comments and whitespace.
_STRIP_COMMENTS = re.compile(
    r"(--[^\n]*)|(/\*.*?\*/)",
    re.DOTALL,
)
_FIRST_KEYWORD = re.compile(r"^\s*(\w+)", re.IGNORECASE)

_ALLOWED_KEYWORDS = {"select", "with"}


def _validate_select_only(sql: str) -> None:
    stripped = _STRIP_COMMENTS.sub("", sql).strip()
    m = _FIRST_KEYWORD.match(stripped)
    if not m or m.group(1).lower() not in _ALLOWED_KEYWORDS:
        raise HTTPException(
            status_code=400,
            detail="Only SELECT (or WITH … SELECT) statements are permitted.",
        )


class SqlBody(BaseModel):
    sql: str
    path: str = "data"


@router.post("")
async def raw_query(
    body: SqlBody,
    qs: QueryService = Depends(get_query_service),
):
    _validate_select_only(body.sql)
    return qs.raw_sql(sql=body.sql, base_path=body.path)
