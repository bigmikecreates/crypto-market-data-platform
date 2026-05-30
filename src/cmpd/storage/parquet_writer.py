from collections import defaultdict
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from cmpd.config import TimestampConfig
from cmpd.models.candle import Candle
from cmpd.models.funding_rate import FundingRate
from cmpd.validation.patterns import _SIGNED_DECIMAL_PATTERN

_DECIMAL128_TYPE = pa.decimal128(38, 10)
_ROW_MERGE_THRESHOLD = 50_000
_CANDLE_KEY_COLS = ["exchange", "symbol", "timeframe", "source", "timestamp"]
_FUNDING_RATE_KEY_COLS = ["exchange", "symbol", "source", "timestamp"]


def _row_key(table: pa.Table, i: int, key_cols: list[str]) -> tuple:
    return tuple(str(table.column(c)[i].as_py()) for c in key_cols)


def _rows_differ(
    t1: pa.Table,
    i1: int,
    t2: pa.Table,
    i2: int,
    data_cols: list[str],
) -> bool:
    for col in data_cols:
        if t1.column(col)[i1].as_py() != t2.column(col)[i2].as_py():
            return True
    return False


def _merge_via_set(
    existing: pa.Table,
    incoming: pa.Table,
    key_cols: list[str],
) -> pa.Table:
    if existing.num_rows == 0:
        return incoming

    all_cols = existing.schema.names
    data_cols = [c for c in all_cols if c not in key_cols]

    incoming_idx_by_key: dict[tuple, int] = {}
    for j in range(incoming.num_rows):
        key = _row_key(incoming, j, key_cols)
        incoming_idx_by_key[key] = j

    existing_idx_by_key: dict[tuple, int] = {}
    keep_indices: list[int] = []
    for i in range(existing.num_rows):
        key = _row_key(existing, i, key_cols)
        existing_idx_by_key[key] = i
        if key not in incoming_idx_by_key:
            keep_indices.append(i)
        else:
            j = incoming_idx_by_key[key]
            if not _rows_differ(existing, i, incoming, j, data_cols):
                keep_indices.append(i)

    new_row_indices: list[int] = []
    for j in range(incoming.num_rows):
        key = _row_key(incoming, j, key_cols)
        if key not in existing_idx_by_key:
            new_row_indices.append(j)
        else:
            i = existing_idx_by_key[key]
            if _rows_differ(existing, i, incoming, j, data_cols):
                new_row_indices.append(j)

    if not new_row_indices and len(keep_indices) == existing.num_rows:
        return existing

    parts: list[pa.Table] = []
    if keep_indices:
        parts.append(existing.take(keep_indices))
    if new_row_indices:
        parts.append(incoming.take(new_row_indices))
    return pa.concat_tables(parts) if len(parts) > 1 else parts[0]


def _merge_via_duckdb(
    existing: pa.Table,
    incoming: pa.Table,
    key_cols: list[str],
) -> pa.Table:
    if existing.num_rows == 0:
        return incoming

    conn = duckdb.connect()
    conn.register("existing", existing)
    conn.register("incoming", incoming)

    join_on = " AND ".join(f"e.{c} = i.{c}" for c in key_cols)
    # Keep existing rows whose key does NOT appear in incoming (anti-join),
    # then append ALL incoming rows. This means incoming always wins on conflict.
    result = conn.execute(f"""
        SELECT e.* FROM existing e
        WHERE NOT EXISTS (
            SELECT 1 FROM incoming i WHERE {join_on}
        )
        UNION ALL
        SELECT * FROM incoming
    """).to_arrow_table()
    conn.close()
    return result


def _merge_tables(
    existing: pa.Table,
    incoming: pa.Table,
    key_cols: list[str],
    strategy: str = "auto",
) -> pa.Table:
    effective = strategy
    if effective == "auto":
        effective = "duckdb" if existing.num_rows >= _ROW_MERGE_THRESHOLD else "memory"
    if effective == "duckdb":
        return _merge_via_duckdb(existing, incoming, key_cols)
    return _merge_via_set(existing, incoming, key_cols)


def _to_decimal128(values: list[str], label: str, candle_key: str) -> pa.Array:
    for v in values:
        if not _SIGNED_DECIMAL_PATTERN.match(v):
            raise ValueError(
                f"Invalid decimal string '{v}' for {label} in candle {candle_key}"
            )
    arr = pa.array(values, type=pa.string())
    return arr.cast(_DECIMAL128_TYPE, safe=False)


def _to_timestamp(
    values: list[str],
    ts_config: TimestampConfig,
) -> pa.Array:
    arr = pa.array(values, type=pa.string())
    return arr.cast(ts_config.parquet_type)


def _path_for_candle(c: Candle, base_path: Path | str) -> Path:
    date_str = c.timestamp[:10]
    return Path(base_path) / c.exchange / c.symbol / c.timeframe / f"{date_str}.parquet"


def candle_to_table(
    candles: list[Candle],
    ts_config: TimestampConfig,
) -> pa.Table:
    if not candles:
        return pa.Table.from_pydict({})

    first = candles[0]
    key = f"{first.exchange}/{first.symbol}/{first.timeframe}"

    return pa.Table.from_pydict(
        {
            "exchange": [c.exchange for c in candles],
            "symbol": [c.symbol for c in candles],
            "timeframe": [c.timeframe for c in candles],
            "timestamp": _to_timestamp([c.timestamp for c in candles], ts_config),
            "open": _to_decimal128([c.open for c in candles], "open", key),
            "high": _to_decimal128([c.high for c in candles], "high", key),
            "low": _to_decimal128([c.low for c in candles], "low", key),
            "close": _to_decimal128([c.close for c in candles], "close", key),
            "volume": _to_decimal128([c.volume for c in candles], "volume", key),
            "source": [c.source for c in candles],
        }
    )


def write_candles(
    candles: list[Candle],
    base_path: Path | str = "data",
    ts_config: TimestampConfig | None = None,
    merge_strategy: str = "auto",
) -> list[Path]:
    if not candles:
        return []

    ts_config = ts_config or TimestampConfig()

    grouped: dict[Path, list[Candle]] = defaultdict(list)
    for c in candles:
        grouped[_path_for_candle(c, base_path)].append(c)

    written: list[Path] = []
    for path, candles_for_path in grouped.items():
        table = candle_to_table(candles_for_path, ts_config)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = pq.read_table(str(path))
            if existing.schema != table.schema:
                existing = existing.cast(table.schema)
            table = _merge_tables(
                existing, table, _CANDLE_KEY_COLS, strategy=merge_strategy
            )

        pq.write_table(table, str(path))
        written.append(path)

    return written


def _path_for_funding_rate(r: FundingRate, base_path: Path | str) -> Path:
    date_str = r.timestamp[:10]
    return (
        Path(base_path) / r.exchange / r.symbol / "funding_rate" / f"{date_str}.parquet"
    )


def funding_rate_to_table(
    rates: list[FundingRate],
    ts_config: TimestampConfig,
) -> pa.Table:
    if not rates:
        return pa.Table.from_pydict({})

    first = rates[0]
    key = f"{first.exchange}/{first.symbol}/funding_rate"

    return pa.Table.from_pydict(
        {
            "exchange": [r.exchange for r in rates],
            "symbol": [r.symbol for r in rates],
            "timestamp": _to_timestamp([r.timestamp for r in rates], ts_config),
            "rate": _to_decimal128([r.rate for r in rates], "rate", key),
            "predicted_rate": _to_decimal128(
                [r.predicted_rate for r in rates], "predicted_rate", key
            ),
            "next_funding_time": _to_timestamp(
                [r.next_funding_time for r in rates], ts_config
            ),
            "source": [r.source for r in rates],
        }
    )


def write_funding_rates(
    rates: list[FundingRate],
    base_path: Path | str = "data",
    ts_config: TimestampConfig | None = None,
    merge_strategy: str = "auto",
) -> list[Path]:
    if not rates:
        return []

    ts_config = ts_config or TimestampConfig()

    grouped: dict[Path, list[FundingRate]] = defaultdict(list)
    for r in rates:
        grouped[_path_for_funding_rate(r, base_path)].append(r)

    written: list[Path] = []
    for path, rates_for_path in grouped.items():
        table = funding_rate_to_table(rates_for_path, ts_config)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = pq.read_table(str(path))
            if existing.schema != table.schema:
                existing = existing.cast(table.schema)
            table = _merge_tables(
                existing, table, _FUNDING_RATE_KEY_COLS, strategy=merge_strategy
            )

        pq.write_table(table, str(path))
        written.append(path)

    return written
