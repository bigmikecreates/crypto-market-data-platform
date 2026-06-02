import logging
import os
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from crmd_platform.config import TimestampConfig
from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.validation.patterns import SIGNED_DECIMAL_PATTERN

LOG = logging.getLogger(__name__)

DECIMAL128_TYPE = pa.decimal128(38, 10)
ROW_MERGE_THRESHOLD = 50_000
CANDLE_KEY_COLS = ["exchange", "symbol", "timeframe", "source", "timestamp"]
FUNDING_RATE_KEY_COLS = ["exchange", "symbol", "source", "timestamp"]

AZURE_SCHEMES = ("az://", "abfs://")


def is_azure(base_path: str) -> bool:
    return base_path.startswith(AZURE_SCHEMES)


def azure_filesystem() -> Any:
    """Build an adlfs filesystem from standard Azure env vars.

    Priority: connection string → account+key → managed identity.
    """
    try:
        import adlfs
    except ImportError:
        raise ImportError(
            "Azure Blob Storage writes require adlfs. "
            "Install with: pip install 'crmd-platform[azure]'"
        )
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        return adlfs.AzureBlobFileSystem(connection_string=conn_str)
    account = os.environ.get("AZURE_STORAGE_ACCOUNT")
    key = os.environ.get("AZURE_STORAGE_KEY")
    # key=None triggers managed-identity / DefaultAzureCredential fallback in adlfs
    return adlfs.AzureBlobFileSystem(account_name=account, account_key=key)


def strip_azure_scheme(uri: str) -> str:
    """Remove az:// or abfs:// prefix, yielding the container/blob path adlfs expects."""
    for scheme in AZURE_SCHEMES:
        if uri.startswith(scheme):
            return uri[len(scheme) :]
    return uri


def uri_for_candle(c: Candle, base: str) -> str:
    """Build a full cloud URI as a plain string.

    Never uses pathlib.Path — POSIX normalisation silently collapses az:// to az:/.
    """
    date_str = c.timestamp[:10]
    return "/".join(
        [base.rstrip("/"), c.exchange, c.symbol, c.timeframe, f"{date_str}.parquet"]
    )


def uri_for_funding_rate(r: FundingRate, base: str) -> str:
    date_str = r.timestamp[:10]
    return "/".join(
        [base.rstrip("/"), r.exchange, r.symbol, "funding_rate", f"{date_str}.parquet"]
    )


def azure_blob_client(fs: Any, blob_path: str) -> Any:
    """Return a BlobClient for ``blob_path`` (container/rest) from an adlfs filesystem."""
    service_client = getattr(fs, "service_client", None)
    if service_client is None:
        raise RuntimeError(
            "Cannot perform Azure Blob lease operations: the filesystem object "
            "does not expose 'service_client'. Ensure adlfs>=2024.7.0 is installed."
        )
    container, _, blob = blob_path.partition("/")
    return service_client.get_blob_client(container=container, blob=blob)


def serialize_table(table: pa.Table) -> bytes:
    """Serialize a PyArrow table to Parquet bytes using the same defaults as pq.write_table."""
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink)
    return sink.getvalue().to_pybytes()


def backoff(attempt: int) -> None:
    time.sleep(min(0.5 * (2**attempt), 8.0) + random.uniform(0, 0.5))


def azure_lease_write(
    table: pa.Table,
    blob_path: str,
    fs: Any,
    key_cols: list[str],
    merge_strategy: str,
    max_attempts: int = 6,
) -> None:
    """Write a Parquet table to Azure Blob Storage with lease-based concurrency control.

    New blobs are written with ``overwrite=False`` (conditional PUT) so that a
    racing creator causes a 409 that this function retries through the lease path.
    Existing blobs are protected by a 30-second Azure Blob lease: only the lease
    holder can upload, so concurrent workers queue rather than overwrite each other.
    """
    from azure.core.exceptions import HttpResponseError

    blob_client = azure_blob_client(fs, blob_path)

    for attempt in range(max_attempts):
        if not fs.exists(blob_path):
            # No blob yet — write conditionally so a racing creator triggers 409.
            try:
                blob_client.upload_blob(serialize_table(table), overwrite=False)
                return
            except HttpResponseError as e:
                if e.status_code != 409:
                    raise
                # Another worker created the blob between our exists() check and write;
                # fall through to the lease path on the next iteration.
        else:
            # Blob exists — acquire an exclusive lease before read-merge-write.
            try:
                lease = blob_client.acquire_lease(lease_duration=30)
            except HttpResponseError as e:
                if e.status_code != 409:
                    raise
                # Another worker holds the lease; back off and retry.
                backoff(attempt)
                continue

            try:
                existing = pq.read_table(blob_path, filesystem=fs)
                if existing.schema != table.schema:
                    existing = existing.cast(table.schema)
                merged = merge_tables(
                    existing, table, key_cols, strategy=merge_strategy
                )
                blob_client.upload_blob(
                    serialize_table(merged), overwrite=True, lease=lease
                )
                return
            finally:
                try:
                    lease.release()
                except Exception:
                    LOG.warning(
                        "Failed to release Azure lease (may have expired)",
                        exc_info=True,
                    )

        backoff(attempt)

    raise RuntimeError(
        f"Could not write to '{blob_path}' after {max_attempts} attempts — "
        "lease contention or transient Azure error"
    )


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


def path_for_candle(c: Candle, base_path: Path | str) -> Path:
    date_str = c.timestamp[:10]
    return Path(base_path) / c.exchange / c.symbol / c.timeframe / f"{date_str}.parquet"


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


def write_candles(
    candles: list[Candle],
    base_path: Path | str = "data",
    ts_config: TimestampConfig | None = None,
    merge_strategy: str = "auto",
) -> Sequence[Path | str]:
    if not candles:
        return []

    ts_config = ts_config or TimestampConfig()

    # ── Azure Blob Storage write path ───────────────────────────────────────
    if is_azure(str(base_path)):
        fs = azure_filesystem()
        grouped_cloud: dict[str, list[Candle]] = defaultdict(list)
        for c in candles:
            grouped_cloud[uri_for_candle(c, str(base_path))].append(c)

        written_uris: list[str] = []
        for uri, candles_for_uri in grouped_cloud.items():
            table = candle_to_table(candles_for_uri, ts_config)
            blob_path = strip_azure_scheme(uri)
            azure_lease_write(table, blob_path, fs, CANDLE_KEY_COLS, merge_strategy)
            written_uris.append(uri)
        return written_uris

    # ── Local write path ────────────────────────────────────────────────────
    grouped: dict[Path, list[Candle]] = defaultdict(list)
    for c in candles:
        grouped[path_for_candle(c, base_path)].append(c)

    written: list[Path] = []
    for path, candles_for_path in grouped.items():
        table = candle_to_table(candles_for_path, ts_config)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = pq.read_table(str(path))
            if existing.schema != table.schema:
                existing = existing.cast(table.schema)
            table = merge_tables(
                existing, table, CANDLE_KEY_COLS, strategy=merge_strategy
            )

        pq.write_table(table, str(path))
        written.append(path)

    return written


def path_for_funding_rate(r: FundingRate, base_path: Path | str) -> Path:
    date_str = r.timestamp[:10]
    return (
        Path(base_path) / r.exchange / r.symbol / "funding_rate" / f"{date_str}.parquet"
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


def write_funding_rates(
    rates: list[FundingRate],
    base_path: Path | str = "data",
    ts_config: TimestampConfig | None = None,
    merge_strategy: str = "auto",
) -> Sequence[Path | str]:
    if not rates:
        return []

    ts_config = ts_config or TimestampConfig()

    # ── Azure Blob Storage write path ───────────────────────────────────────
    if is_azure(str(base_path)):
        fs = azure_filesystem()
        grouped_cloud: dict[str, list[FundingRate]] = defaultdict(list)
        for r in rates:
            grouped_cloud[uri_for_funding_rate(r, str(base_path))].append(r)

        written_uris: list[str] = []
        for uri, rates_for_uri in grouped_cloud.items():
            table = funding_rate_to_table(rates_for_uri, ts_config)
            blob_path = strip_azure_scheme(uri)
            azure_lease_write(
                table, blob_path, fs, FUNDING_RATE_KEY_COLS, merge_strategy
            )
            written_uris.append(uri)
        return written_uris

    # ── Local write path ────────────────────────────────────────────────────
    grouped: dict[Path, list[FundingRate]] = defaultdict(list)
    for r in rates:
        grouped[path_for_funding_rate(r, base_path)].append(r)

    written: list[Path] = []
    for path, rates_for_path in grouped.items():
        table = funding_rate_to_table(rates_for_path, ts_config)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = pq.read_table(str(path))
            if existing.schema != table.schema:
                existing = existing.cast(table.schema)
            table = merge_tables(
                existing, table, FUNDING_RATE_KEY_COLS, strategy=merge_strategy
            )

        pq.write_table(table, str(path))
        written.append(path)

    return written
