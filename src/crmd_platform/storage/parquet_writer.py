import logging
from collections import defaultdict
from pathlib import Path
from typing import Sequence

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from crmd_platform.config import TimestampConfig
from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.storage.backend import StorageBackend, create_backend
from crmd_platform.validation.patterns import SIGNED_DECIMAL_PATTERN

LOG = logging.getLogger(__name__)

DECIMAL128_TYPE = pa.decimal128(38, 10)
ROW_MERGE_THRESHOLD = 50_000
CANDLE_KEY_COLS = ["exchange", "symbol", "timeframe", "source", "timestamp"]
FUNDING_RATE_KEY_COLS = ["exchange", "symbol", "source", "timestamp"]


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


def merge_via_set(
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


def merge_via_duckdb(
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
    # then append ALL incoming rows. Incoming always wins on key conflict.
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


_VALID_MERGE_STRATEGIES = ("auto", "memory", "duckdb")


def merge_tables(
    existing: pa.Table,
    incoming: pa.Table,
    key_cols: list[str],
    strategy: str = "auto",
) -> pa.Table:
    if strategy not in _VALID_MERGE_STRATEGIES:
        raise ValueError(
            f"merge_strategy must be one of {_VALID_MERGE_STRATEGIES}, got {strategy!r}"
        )
    effective = strategy
    if effective == "auto":
        effective = "duckdb" if existing.num_rows >= ROW_MERGE_THRESHOLD else "memory"
    if effective == "duckdb":
        return merge_via_duckdb(existing, incoming, key_cols)
    return merge_via_set(existing, incoming, key_cols)


def to_decimal128(values: list[str], label: str, candle_key: str) -> pa.Array:
    for v in values:
        if not SIGNED_DECIMAL_PATTERN.match(v):
            raise ValueError(
                f"Invalid decimal string '{v}' for {label} in candle {candle_key}"
            )
    arr = pa.array(values, type=pa.string())
    return arr.cast(DECIMAL128_TYPE, safe=False)


def to_timestamp(
    values: list[str],
    ts_config: TimestampConfig,
) -> pa.Array:
    arr = pa.array(values, type=pa.string())
    return arr.cast(ts_config.parquet_type)


def candle_to_table(
    candles: list[Candle],
    ts_config: TimestampConfig,
) -> pa.Table:
    if not candles:
        return pa.Table.from_pydict(
            {
                "exchange": [],
                "symbol": [],
                "timeframe": [],
                "timestamp": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
                "source": [],
            },
            schema=pa.schema(
                [
                    pa.field("exchange", pa.string()),
                    pa.field("symbol", pa.string()),
                    pa.field("timeframe", pa.string()),
                    pa.field("timestamp", ts_config.parquet_type),
                    pa.field("open", DECIMAL128_TYPE),
                    pa.field("high", DECIMAL128_TYPE),
                    pa.field("low", DECIMAL128_TYPE),
                    pa.field("close", DECIMAL128_TYPE),
                    pa.field("volume", DECIMAL128_TYPE),
                    pa.field("source", pa.string()),
                ]
            ),
        )

    first = candles[0]
    key = f"{first.exchange}/{first.symbol}/{first.timeframe}"

    return pa.Table.from_pydict(
        {
            "exchange": [c.exchange for c in candles],
            "symbol": [c.symbol for c in candles],
            "timeframe": [c.timeframe for c in candles],
            "timestamp": to_timestamp([c.timestamp for c in candles], ts_config),
            "open": to_decimal128([c.open for c in candles], "open", key),
            "high": to_decimal128([c.high for c in candles], "high", key),
            "low": to_decimal128([c.low for c in candles], "low", key),
            "close": to_decimal128([c.close for c in candles], "close", key),
            "volume": to_decimal128([c.volume for c in candles], "volume", key),
            "source": [c.source for c in candles],
        }
    )


def funding_rate_to_table(
    rates: list[FundingRate],
    ts_config: TimestampConfig,
) -> pa.Table:
    if not rates:
        return pa.Table.from_pydict(
            {
                "exchange": [],
                "symbol": [],
                "timestamp": [],
                "rate": [],
                "predicted_rate": [],
                "next_funding_time": [],
                "source": [],
            },
            schema=pa.schema(
                [
                    pa.field("exchange", pa.string()),
                    pa.field("symbol", pa.string()),
                    pa.field("timestamp", ts_config.parquet_type),
                    pa.field("rate", DECIMAL128_TYPE),
                    pa.field("predicted_rate", DECIMAL128_TYPE),
                    pa.field("next_funding_time", ts_config.parquet_type),
                    pa.field("source", pa.string()),
                ]
            ),
        )

    first = rates[0]
    key = f"{first.exchange}/{first.symbol}/funding_rate"

    return pa.Table.from_pydict(
        {
            "exchange": [r.exchange for r in rates],
            "symbol": [r.symbol for r in rates],
            "timestamp": to_timestamp([r.timestamp for r in rates], ts_config),
            "rate": to_decimal128([r.rate for r in rates], "rate", key),
            "predicted_rate": to_decimal128(
                [r.predicted_rate for r in rates], "predicted_rate", key
            ),
            "next_funding_time": to_timestamp(
                [r.next_funding_time for r in rates], ts_config
            ),
            "source": [r.source for r in rates],
        }
    )


def write_candles(
    candles: list[Candle],
    base_path: Path | str = "data",
    ts_config: TimestampConfig | None = None,
    merge_strategy: str = "auto",
    backend: StorageBackend | None = None,
) -> Sequence[Path | str]:
    """Write candles to storage.

    Args:
        candles: List of candles to write
        base_path: Storage path (local path or cloud URI). Ignored if backend is provided.
        ts_config: Timestamp configuration
        merge_strategy: Merge strategy for existing data ("auto", "memory", "duckdb")
        backend: Storage backend instance. If None, created from base_path.

    Returns:
        List of written file paths
    """
    if not candles:
        return []

    ts_config = ts_config or TimestampConfig()

    # Create backend if not provided
    if backend is None:
        backend = create_backend(str(base_path))

    # Group candles by target path
    grouped: dict[str, list[Candle]] = defaultdict(list)
    for c in candles:
        date_str = c.timestamp[:10]
        path = backend.join_path(
            str(base_path), c.exchange, c.symbol, c.timeframe, f"{date_str}.parquet"
        )
        grouped[path].append(c)

    written: list[Path | str] = []
    for path, candles_for_path in grouped.items():
        table = candle_to_table(candles_for_path, ts_config)
        backend.ensure_dir(path)

        def merge_fn(existing: pa.Table, table=table) -> pa.Table:
            if existing.schema != table.schema:
                existing = existing.cast(table.schema)
            return merge_tables(existing, table, CANDLE_KEY_COLS, strategy=merge_strategy)

        backend.write_parquet_with_lease(path, table, merge_fn)
        written.append(backend.wrap_path(path))

    return written


def write_funding_rates(
    rates: list[FundingRate],
    base_path: Path | str = "data",
    ts_config: TimestampConfig | None = None,
    merge_strategy: str = "auto",
    backend: StorageBackend | None = None,
) -> Sequence[Path | str]:
    """Write funding rates to storage.

    Args:
        rates: List of funding rates to write
        base_path: Storage path (local path or cloud URI). Ignored if backend is provided.
        ts_config: Timestamp configuration
        merge_strategy: Merge strategy for existing data ("auto", "memory", "duckdb")
        backend: Storage backend instance. If None, created from base_path.

    Returns:
        List of written file paths
    """
    if not rates:
        return []

    ts_config = ts_config or TimestampConfig()

    # Create backend if not provided
    if backend is None:
        backend = create_backend(str(base_path))

    # Group rates by target path
    grouped: dict[str, list[FundingRate]] = defaultdict(list)
    for r in rates:
        date_str = r.timestamp[:10]
        path = backend.join_path(
            str(base_path), r.exchange, r.symbol, "funding_rate", f"{date_str}.parquet"
        )
        grouped[path].append(r)

    written: list[Path | str] = []
    for path, rates_for_path in grouped.items():
        table = funding_rate_to_table(rates_for_path, ts_config)
        backend.ensure_dir(path)

        def merge_fn(existing: pa.Table, table=table) -> pa.Table:
            if existing.schema != table.schema:
                existing = existing.cast(table.schema)
            return merge_tables(
                existing, table, FUNDING_RATE_KEY_COLS, strategy=merge_strategy
            )

        backend.write_parquet_with_lease(path, table, merge_fn)
        written.append(backend.wrap_path(path))

    return written
