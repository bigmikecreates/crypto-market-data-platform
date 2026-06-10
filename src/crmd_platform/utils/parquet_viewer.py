from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

_TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
]


def parse_timestamp(s: str) -> int:
    for fmt in _TIMESTAMP_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    raise ValueError(f"Unable to parse timestamp '{s}'. Use ISO-8601 format.")


def discover_files(path_str: str) -> list[Path]:
    p = Path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"Path does not exist: {p}")
    if p.is_file():
        if p.suffix != ".parquet":
            raise ValueError(f"Not a parquet file: {p}")
        return [p]
    files = sorted(p.rglob("*.parquet"))
    if not files:
        raise ValueError(f"No parquet files found under {p}")
    return files


def read_and_filter(
    files: list[Path],
    range_start_ts: int | None,
    range_end_ts: int | None,
) -> pa.Table:
    tables = [pq.read_table(str(f)) for f in files]
    table = tables[0] if len(tables) == 1 else pa.concat_tables(tables)

    if range_start_ts is not None or range_end_ts is not None:
        ts_col = table.column("timestamp")
        mask = pa.array([True] * len(table), type=pa.bool_())
        if range_start_ts is not None:
            start_scalar = pa.scalar(range_start_ts, type=pa.timestamp("s"))
            mask = pc.and_(mask, pc.greater_equal(ts_col, start_scalar))  # type: ignore[attr-defined]
        if range_end_ts is not None:
            end_scalar = pa.scalar(range_end_ts, type=pa.timestamp("s"))
            mask = pc.and_(mask, pc.less(ts_col, end_scalar))  # type: ignore[attr-defined]
        table = table.filter(mask)

    return table


def get_schema_info(table: pa.Table) -> list[tuple[str, str]]:
    return [(f.name, str(f.type)) for f in table.schema]


def get_column_stats(table: pa.Table) -> list[dict[str, Any]]:
    stats = []
    for col_name in table.column_names:
        col = table.column(col_name)
        info: dict[str, Any] = {"name": col_name, "nulls": col.null_count}
        if pa.types.is_decimal(col.type):
            try:
                min_val = pc.min(col)  # type: ignore[attr-defined]
                max_val = pc.max(col)  # type: ignore[attr-defined]
                if min_val.is_valid:
                    info["min"] = str(min_val.as_py())
                if max_val.is_valid:
                    info["max"] = str(max_val.as_py())
            except Exception:
                pass
        stats.append(info)
    return stats


def get_metadata_info(path: Path) -> dict[str, Any]:
    meta = pq.read_metadata(str(path))
    rg_list = []
    for i in range(meta.num_row_groups):
        rg = meta.row_group(i)
        col0 = rg.column(0) if rg.num_columns > 0 else None
        rg_list.append(
            {
                "rows": rg.num_rows,
                "total_byte_size": rg.total_byte_size,
                "compression": col0.compression if col0 else "unknown",
            }
        )
    return {
        "rows": meta.num_rows,
        "row_groups": meta.num_row_groups,
        "created_by": meta.created_by or "unknown",
        "columns": meta.num_columns,
        "row_group_details": rg_list,
    }


def table_to_dicts(table: pa.Table, limit: int) -> list[dict[str, str]]:
    n = min(len(table), limit)
    rows = []
    for i in range(n):
        row = {}
        for col_name in table.column_names:
            val = table.column(col_name)[i].as_py()
            if val is None:
                row[col_name] = "NULL"
            elif isinstance(val, datetime):
                row[col_name] = val.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                s = str(val)
                if "." in s:
                    s = s.rstrip("0").rstrip(".")
                row[col_name] = s
        rows.append(row)
    return rows


def format_table(rows: list[dict[str, str]], columns: list[str] | None = None) -> str:
    if not rows:
        return "  (no rows)"
    if columns is None:
        columns = list(rows[0].keys())

    widths = [max(len(c), max(len(r[c]) for r in rows)) for c in columns]

    lines: list[str] = []
    header = " │ ".join(f"{c:{w}}" for c, w in zip(columns, widths))
    lines.append(f"  {header}")
    sep = " │ ".join("─" * w for w in widths)
    lines.append(f"  {sep}")
    for r in rows:
        vals = " │ ".join(f"{r[c]:{w}}" for c, w in zip(columns, widths))
        lines.append(f"  {vals}")
    return "\n".join(lines)


def run_inspect(
    path_str: str,
    limit: int = 10,
    start: str | None = None,
    end: str | None = None,
    show_stats: bool = False,
    show_verbose: bool = False,
) -> str:
    files = discover_files(path_str)

    range_start_ts = parse_timestamp(start) if start else None
    range_end_ts = parse_timestamp(end) if end else None

    table = read_and_filter(files, range_start_ts, range_end_ts)

    lines: list[str] = []

    display_path = path_str
    if len(files) == 1:
        lines.append(f"File: {files[0]}")
    else:
        lines.append(f"Directory: {display_path}")
        lines.append(f"Files: {len(files)}")
    lines.append(f"Rows: {len(table)}")
    lines.append("")

    schema_info = get_schema_info(table)
    lines.append("Schema:")
    max_name_len = max(len(name) for name, _ in schema_info)
    for name, typ in schema_info:
        lines.append(f"  {name:{max_name_len}}  {typ}")
    lines.append("")

    if show_stats:
        all_stats = get_column_stats(table)
        numeric_stats = [s for s in all_stats if "min" in s or "max" in s]
        if numeric_stats:
            lines.append("Statistics:")
            for s in numeric_stats:
                parts = [f"  {s['name']}"]
                if "min" in s:
                    parts.append(f"  min={s['min']}")
                if "max" in s:
                    parts.append(f"  max={s['max']}")
                parts.append(f"  nulls={s['nulls']}")
                lines.append("".join(parts))
            lines.append("")

    sample_rows = table_to_dicts(table, limit)
    label = f"Sample (first {len(sample_rows)}):"
    lines.append(label)
    columns = list(table.schema.names)
    lines.append(format_table(sample_rows, columns))
    lines.append("")

    if show_verbose and len(files) == 1:
        meta = get_metadata_info(files[0])
        lines.append("Metadata:")
        lines.append(f"  Created by:     {meta['created_by']}")
        lines.append(f"  Row groups:     {meta['row_groups']}")
        lines.append(f"  Groups/columns: {meta['columns']}")
        for i, rg in enumerate(meta.get("row_group_details", [])):
            lines.append(
                f"  Group {i}:       {rg['rows']} rows, {rg['total_byte_size']} bytes, {rg['compression']}"
            )

    return "\n".join(lines)
