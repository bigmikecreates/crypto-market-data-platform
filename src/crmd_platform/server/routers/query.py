import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from crmd_platform.query import QueryService
from crmd_platform.server.dependencies import get_base_path, get_query_service

router = APIRouter(prefix="/query", tags=["query"])

# Matches the first SQL keyword after stripping comments and whitespace.
_STRIP_COMMENTS = re.compile(
    r"(--[^\n]*)|(/\*.*?\*/)",
    re.DOTALL,
)
_FIRST_KEYWORD = re.compile(r"^\s*(\w+)", re.IGNORECASE)

_ALLOWED_KEYWORDS = {"select", "with"}


def has_multiple_statements(sql: str) -> bool:
    """Return True if sql contains a semicolon outside of a string literal.

    Tracks single-quoted and double-quoted string context so that semicolons
    inside string values (e.g. WHERE col = 'a;b') are not treated as statement
    separators.  Escaped single-quotes ('') are handled correctly.
    """
    in_single = False
    in_double = False
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'" and not in_double:
            if in_single and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2  # escaped '' — stay inside the string
                continue
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == ";" and not in_single and not in_double:
            return True
        i += 1
    return False


def validate_select_only(sql: str) -> None:
    stripped = _STRIP_COMMENTS.sub("", sql).strip()
    m = _FIRST_KEYWORD.match(stripped)
    if not m or m.group(1).lower() not in _ALLOWED_KEYWORDS:
        raise HTTPException(
            status_code=400,
            detail="Only SELECT (or WITH … SELECT) statements are permitted.",
        )
    if has_multiple_statements(stripped):
        raise HTTPException(
            status_code=400,
            detail="Multiple SQL statements are not permitted.",
        )


class SqlBody(BaseModel):
    sql: str


@router.post("")
async def raw_query(
    body: SqlBody,
    base_path: str = Depends(get_base_path),
    qs: QueryService = Depends(get_query_service),
):
    validate_select_only(body.sql)
    return qs.raw_sql(sql=body.sql, base_path=base_path)
