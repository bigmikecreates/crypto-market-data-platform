from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate
from crypto_market_data_platform.query.service import QueryService


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


def _discover_files(
    base_path: str,
) -> dict[str, dict[str, list[Path]]]:
    """Discover parquet files grouped by type, then by dataset path.

    Path conventions:
      Candles:      {base}/{exchange}/{symbol...}/{timeframe}/{date}.parquet
      Funding rate: {base}/{exchange}/{symbol...}/funding_rate/{date}.parquet

    Symbol may contain '/' (e.g. BTC/USDT), so path depth varies.
    The anchor is the penultimate component: timeframe or 'funding_rate'.

    Returns e.g.:
      {"candle": {"ex_a/BTC/USDT/1h": [Path(...), ...]},
       "funding_rate": {"ex_a/PI_XBTUSD/funding_rate": [Path(...), ...]}}
    """
    all_files = sorted(Path(base_path).rglob("*.parquet"))
    candles: dict[str, list[Path]] = {}
    funding: dict[str, list[Path]] = {}

    for f in all_files:
        parts = f.relative_to(base_path).parts
        anchor = parts[-2]
        exchange = parts[0]
        if anchor == "funding_rate":
            symbol = "/".join(parts[1:-2])
            key = f"{exchange}/{symbol}/funding_rate"
            funding.setdefault(key, []).append(f)
        else:
            timeframe = anchor
            symbol = "/".join(parts[1:-2])
            key = f"{exchange}/{symbol}/{timeframe}"
            candles.setdefault(key, []).append(f)

    result: dict[str, dict[str, list[Path]]] = {}
    if candles:
        result["candle"] = candles
    if funding:
        result["funding_rate"] = funding
    return result


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
            result = con.sql(sql)
            dicts = _rows_to_dicts(result)
            return [FundingRate(**d) for d in dicts]
        finally:
            con.close()

    def get_summary(self, base_path: str = "data") -> list[dict[str, Any]]:
        tables = _discover_files(base_path)
        rows: list[dict[str, Any]] = []
        con = duckdb.connect()
        try:
            for type_name, datasets in tables.items():
                for dataset_key, files in datasets.items():
                    paths = ", ".join(f"'{f}'" for f in files)
                    sql = f"SELECT COUNT(*) AS cnt FROM read_parquet([{paths}])"
                    result = con.sql(sql)
                    row = result.fetchone()
                    count = row[0] if row is not None else 0
                    parts = dataset_key.split("/")
                    if type_name == "candle":
                        exchange, symbol, timeframe = parts[0], parts[1], parts[2]
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
                        exchange, symbol = parts[0], parts[1]
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
        finally:
            con.close()
        return rows

    def raw_sql(self, sql: str, base_path: str = "data") -> list[dict[str, Any]]:
        con = duckdb.connect()
        try:
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
    ) -> list[Path]:
        tables = _discover_files(base_path)
        datasets = tables.get(data_type, {})
        candidates: list[str] = list(datasets.keys())

        if exchange:
            candidates = [k for k in candidates if k.startswith(f"{exchange}/")]
        if data_type == "candle" and timeframe:
            candidates = [k for k in candidates if k.endswith(f"/{timeframe}")]
        if symbol:
            candidates = [
                k for k in candidates if f"/{symbol}" in k or k.startswith(f"{symbol}/")
            ]

        result: list[Path] = []
        for key in candidates:
            result.extend(datasets[key])
        return result

    @staticmethod
    def _build_query(
        files: list[Path],
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> str:
        paths = ", ".join(f"'{f}'" for f in files)
        clauses: list[str] = []
        if start:
            clauses.append(f"timestamp >= '{start}'")
        if end:
            clauses.append(f"timestamp < '{end}'")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return (
            f"SELECT * FROM read_parquet([{paths}]){where}"
            f" ORDER BY timestamp {order} LIMIT {limit}"
        )
