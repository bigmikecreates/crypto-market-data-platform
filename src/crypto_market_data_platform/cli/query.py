from pathlib import Path
from typing import Any

from crypto_market_data_platform.query.duckdb_service import DuckDBQueryService


def discover_files(
    base_path: str,
    data_type: str = "all",
) -> dict[str, list[Path]]:
    svc = DuckDBQueryService()
    datasets = svc.list_datasets(base_path)
    result: dict[str, list[Path]] = {}
    for type_name in datasets:
        if data_type != "all" and type_name != data_type:
            continue
        files: list[Path] = []
        for key in datasets[type_name]:
            ftype = type_name
            parts = key.split("/")
            if ftype == "candle":
                ex, sym, tf = parts[0], parts[1], parts[2]
                glob_path = Path(base_path) / ex / sym / tf / "*.parquet"
            else:
                ex, sym = parts[0], parts[1]
                glob_path = Path(base_path) / ex / sym / "funding_rate" / "*.parquet"
            files.extend(sorted(glob_path.parent.glob("*.parquet")))
        if files:
            result[type_name] = files
    return result


def run_query(
    files: list[Path],
    sql: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    svc = DuckDBQueryService()
    if sql:
        return svc.raw_sql(sql)
    if not files:
        return []
    paths = ", ".join(f"'{f}'" for f in files)
    query = f"SELECT * FROM read_parquet([{paths}]) ORDER BY timestamp DESC LIMIT {limit}"
    return svc.raw_sql(query)
