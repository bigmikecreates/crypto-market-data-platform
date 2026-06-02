import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from crmd_platform.config import CLOUD_SCHEMES
from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.query.service import QueryService

# Blocked DuckDB functions that could read arbitrary filesystem files.
# read_parquet is intentionally allowed — the whole point of raw_sql is to query Parquet data.
# Functions like read_csv, read_text, read_blob expose the local filesystem.
_BLOCKED_FUNCTIONS = re.compile(
    r"\b("
    r"read_csv|read_csv_auto|read_text|read_blob|read_json|read_json_auto"
    r"|glob|lsfs|file_"
    r"|load|install|copy_database|backup"
    r")\s*\(",
    re.IGNORECASE,
)


def _rows_to_dicts(sql_result: Any) -> list[dict[str, Any]]:
    columns = [desc[0] for desc in sql_result.description]
    rows = sql_result.fetchall()
    return [
        {
            col: (
                val.isoformat()
                if isinstance(val, datetime)
                else str(val)
                if isinstance(val, Decimal)
                else val
            )
            for col, val in zip(columns, row)
        }
        for row in rows
    ]


# Accepts ISO-8601 dates (2025-01-15) and datetimes (2025-01-15T12:00 / 2025-01-15T12:00:00).
# Tight enough to prevent any SQL injection via start/end parameters.
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$")


def assert_safe_timestamp(value: str, name: str) -> None:
    if not _TIMESTAMP_RE.match(value):
        raise ValueError(
            f"{name!r} must be an ISO-8601 date or datetime "
            f"(e.g. '2025-01-15' or '2025-01-15T12:00:00'), got {value!r}"
        )


def _is_cloud(path: str) -> bool:
    return path.startswith(CLOUD_SCHEMES)


def _configure_connection(con: duckdb.DuckDBPyConnection, base_path: str) -> None:
    """Load the DuckDB extension appropriate for the storage scheme."""
    if base_path.startswith(("s3://", "gs://")):
        con.execute("INSTALL httpfs; LOAD httpfs;")
    elif base_path.startswith(("az://", "abfs://")):
        con.execute("INSTALL azure; LOAD azure;")


def _relative_parts(uri: str, base: str) -> tuple[str, ...]:
    """Return path components of `uri` relative to `base`."""
    prefix = base.rstrip("/") + "/"
    tail = uri[len(prefix):]
    return tuple(p for p in tail.split("/") if p)


def _parse_into_buckets(
    uri: str,
    base_path: str,
    candles: dict[str, list[str]],
    funding: dict[str, list[str]],
) -> None:
    parts = _relative_parts(uri, base_path)
    if len(parts) < 3:
        return
    anchor = parts[-2]
    exchange = parts[0]
    if anchor == "funding_rate":
        symbol = "/".join(parts[1:-2])
        key = f"{exchange}/{symbol}/funding_rate"
        funding.setdefault(key, []).append(uri)
    else:
        symbol = "/".join(parts[1:-2])
        key = f"{exchange}/{symbol}/{anchor}"
        candles.setdefault(key, []).append(uri)


def discover_files_local(base_path: str) -> dict[str, dict[str, list[str]]]:
    candles: dict[str, list[str]] = {}
    funding: dict[str, list[str]] = {}
    for f in sorted(Path(base_path).rglob("*.parquet")):
        _parse_into_buckets(str(f), base_path, candles, funding)
    result: dict[str, dict[str, list[str]]] = {}
    if candles:
        result["candle"] = candles
    if funding:
        result["funding_rate"] = funding
    return result


def _discover_files_cloud(base_path: str) -> dict[str, dict[str, list[str]]]:
    con = duckdb.connect()
    try:
        _configure_connection(con, base_path)
        pattern = base_path.rstrip("/") + "/**/*.parquet"
        rows = con.execute("SELECT file FROM glob(?)", [pattern]).fetchall()
    finally:
        con.close()

    candles: dict[str, list[str]] = {}
    funding: dict[str, list[str]] = {}
    for (uri,) in rows:
        _parse_into_buckets(uri, base_path, candles, funding)

    result: dict[str, dict[str, list[str]]] = {}
    if candles:
        result["candle"] = candles
    if funding:
        result["funding_rate"] = funding
    return result


def _discover_files(base_path: str) -> dict[str, dict[str, list[str]]]:
    if _is_cloud(base_path):
        return _discover_files_cloud(base_path)
    return discover_files_local(base_path)


class DuckDBQueryService(QueryService):
    def list_datasets(self, base_path: str = "data") -> dict[str, list[str]]:
        files = _discover_files(base_path)
        return {k: sorted(v.keys()) for k, v in files.items()}

    def get_candles(
        self,
        base_path: str = "data",
        exchange: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[Candle]:
        files = self._resolve_files(base_path, "candle", exchange, symbol, timeframe)
        if not files:
            return []
        sql = self._build_query(files, start, end, limit, order)
        con = duckdb.connect()
        try:
            _configure_connection(con, base_path)
            result = con.sql(sql)
            dicts = _rows_to_dicts(result)
            return [Candle(**d) for d in dicts]
        finally:
            con.close()

    def get_funding_rates(
        self,
        base_path: str = "data",
        exchange: str | None = None,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[FundingRate]:
        files = self._resolve_files(base_path, "funding_rate", exchange, symbol)
        if not files:
            return []
        sql = self._build_query(files, start, end, limit, order)
        con = duckdb.connect()
        try:
            _configure_connection(con, base_path)
            result = con.sql(sql)
            dicts = _rows_to_dicts(result)
            return [FundingRate(**d) for d in dicts]
        finally:
            con.close()

    def get_summary(self, base_path: str = "data") -> list[dict[str, Any]]:
        tables = _discover_files(base_path)
        rows: list[dict[str, Any]] = []
        for type_name, datasets in tables.items():
            for dataset_key, files in datasets.items():
                # Use a fresh connection per dataset so a bad Parquet file in one
                # dataset cannot abort the transaction and silently truncate the rest.
                con = duckdb.connect()
                try:
                    _configure_connection(con, base_path)
                    paths = ", ".join(f"'{f}'" for f in files)
                    sql = f"SELECT COUNT(*) AS cnt FROM read_parquet([{paths}])"
                    result = con.sql(sql)
                    row = result.fetchone()
                    count = row[0] if row is not None else 0
                except Exception:
                    count = 0
                finally:
                    con.close()

                parts = dataset_key.split("/")
                exchange = parts[0]
                if type_name == "candle":
                    # dataset_key = "exchange/sym/possibly/multi/part/timeframe"
                    timeframe = parts[-1]
                    symbol = "/".join(parts[1:-1])
                    rows.append(
                        {
                            "type": "candle",
                            "exchange": exchange,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "files": len(files),
                            "rows": int(count),
                        }
                    )
                else:
                    # dataset_key = "exchange/sym/possibly/multi/part/funding_rate"
                    symbol = "/".join(parts[1:-1])
                    rows.append(
                        {
                            "type": "funding_rate",
                            "exchange": exchange,
                            "symbol": symbol,
                            "timeframe": None,
                            "files": len(files),
                            "rows": int(count),
                        }
                    )
        return rows

    def raw_sql(self, sql: str, base_path: str = "data") -> list[dict[str, Any]]:
        if _BLOCKED_FUNCTIONS.search(sql):
            raise ValueError("Query contains blocked functions (read_csv, read_text, read_blob, etc.)")
        con = duckdb.connect()
        try:
            _configure_connection(con, base_path)
            result = con.sql(sql)
            return _rows_to_dicts(result)
        finally:
            con.close()

    def _resolve_files(
        self,
        base_path: str,
        data_type: str,
        exchange: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[str]:
        tables = _discover_files(base_path)
        datasets = tables.get(data_type, {})
        candidates: list[str] = list(datasets.keys())

        if exchange:
            candidates = [k for k in candidates if k.startswith(f"{exchange}/")]
        if data_type == "candle" and timeframe:
            candidates = [k for k in candidates if k.endswith(f"/{timeframe}")]
        if symbol:
            # Exact component match: key = "exchange/sym1/.../symN/timeframe_or_funding_rate"
            # The symbol occupies parts[1:-1]. Substring matching (f"/{symbol}" in k) was
            # wrong for short suffixes like "USDT" matching "BTC/USDT".
            def _symbol_matches(key: str) -> bool:
                parts = key.split("/")
                return "/".join(parts[1:-1]) == symbol

            candidates = [k for k in candidates if _symbol_matches(k)]

        result: list[str] = []
        for key in candidates:
            result.extend(datasets[key])
        return result

    @staticmethod
    def _build_query(
        files: list[str],
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> str:
        if order not in ("ASC", "DESC"):
            raise ValueError(f"order must be 'ASC' or 'DESC', got {order!r}")
        paths = ", ".join(f"'{f}'" for f in files)
        clauses: list[str] = []
        if start:
            assert_safe_timestamp(start, "start")
            clauses.append(f"timestamp >= '{start}'")
        if end:
            assert_safe_timestamp(end, "end")
            clauses.append(f"timestamp < '{end}'")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return (
            f"SELECT * FROM read_parquet([{paths}]){where}"
            f" ORDER BY timestamp {order} LIMIT {limit}"
        )
