"""
Property-based tests for storage correctness.

Three core properties:
  1. Roundtrip — write then read preserves row count and key field values.
  2. Merge idempotence — merge(A, A) == A for both strategies.
  3. Merge key uniqueness — merged result has no duplicate primary keys.
"""

import tempfile

import pyarrow.parquet as pq
from hypothesis import given, settings
from hypothesis import strategies as st

from crmd_platform.config import TimestampConfig
from crmd_platform.models.candle import Candle
from crmd_platform.storage import create_backend
from crmd_platform.storage.parquet_writer import (
    CANDLE_KEY_COLS,
    merge_via_duckdb,
    merge_via_set,
    candle_to_table,
    write_candles,
)

_TS_CONFIG = TimestampConfig()

# ── Shared strategy (duplicated from test_validation_properties for isolation) ─


def _fmt(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


_positive_cents = st.integers(min_value=1, max_value=10_000_000)
_non_negative_cents = st.integers(min_value=0, max_value=10_000_000)


@st.composite
def _valid_candle(draw, timestamp: str) -> Candle:
    low_cents = draw(_positive_cents)
    high_cents = draw(st.integers(min_value=low_cents, max_value=low_cents + 1_000_000))
    open_cents = draw(st.integers(min_value=low_cents, max_value=high_cents))
    close_cents = draw(st.integers(min_value=low_cents, max_value=high_cents))
    volume_cents = draw(_non_negative_cents)
    return Candle(
        exchange="test",
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=timestamp,
        open=_fmt(open_cents),
        high=_fmt(high_cents),
        low=_fmt(low_cents),
        close=_fmt(close_cents),
        volume=_fmt(volume_cents),
        source="test",
    )


@st.composite
def candle_list(draw, min_size: int = 1, max_size: int = 20) -> list[Candle]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    hours = draw(
        st.lists(
            st.integers(min_value=0, max_value=23), min_size=n, max_size=n, unique=True
        )
    )
    return [draw(_valid_candle(timestamp=f"2024-01-01T{h:02d}:00:00")) for h in hours]


# ── Roundtrip properties ──────────────────────────────────────────


@given(candle_list(min_size=1, max_size=20))
@settings(max_examples=50, deadline=None)
def test_write_read_preserves_row_count(candles: list[Candle]) -> None:
    """Total rows in all written files must equal the number of candles."""
    with tempfile.TemporaryDirectory() as tmp:
        written = write_candles(candles, base_path=tmp, backend=create_backend(tmp))
        assert len(written) >= 1
        total_rows = sum(pq.read_table(str(p)).num_rows for p in written)
        assert total_rows == len(candles)


@given(candle_list(min_size=1, max_size=20))
@settings(max_examples=50, deadline=None)
def test_write_twice_same_data_no_duplicates(candles: list[Candle]) -> None:
    """Writing the same batch twice must not create duplicate rows."""
    with tempfile.TemporaryDirectory() as tmp:
        write_candles(candles, base_path=tmp, backend=create_backend(tmp))
        write_candles(candles, base_path=tmp, backend=create_backend(tmp))
        written = list(__import__("pathlib").Path(tmp).rglob("*.parquet"))
        total_rows = sum(pq.read_table(str(p)).num_rows for p in written)
        assert total_rows == len(candles)


@given(candle_list(min_size=1, max_size=20))
@settings(max_examples=50, deadline=None)
def test_written_candles_have_correct_exchange_and_symbol(
    candles: list[Candle],
) -> None:
    """Every row in written Parquet files must have the correct exchange and symbol."""
    with tempfile.TemporaryDirectory() as tmp:
        written = write_candles(candles, base_path=tmp, backend=create_backend(tmp))
        for path in written:
            table = pq.read_table(str(path))
            exchanges = set(table.column("exchange").to_pylist())
            symbols = set(table.column("symbol").to_pylist())
            assert exchanges == {"test"}
            assert symbols == {"BTC/USDT"}


# ── Merge idempotence ─────────────────────────────────────────────


@given(candle_list(min_size=1, max_size=20))
def test_merge_set_idempotent(candles: list[Candle]) -> None:
    """merge_via_set(A, A) must return exactly the same number of rows as A."""
    table = candle_to_table(candles, _TS_CONFIG)
    merged = merge_via_set(table, table, CANDLE_KEY_COLS)
    assert merged.num_rows == table.num_rows


@given(candle_list(min_size=1, max_size=20))
def test_merge_duckdb_idempotent(candles: list[Candle]) -> None:
    """merge_via_duckdb(A, A) must return exactly the same number of rows as A."""
    table = candle_to_table(candles, _TS_CONFIG)
    merged = merge_via_duckdb(table, table, CANDLE_KEY_COLS)
    assert merged.num_rows == table.num_rows


# ── Merge key uniqueness ──────────────────────────────────────────


@given(candle_list(min_size=1, max_size=10), candle_list(min_size=1, max_size=10))
@settings(max_examples=50, deadline=None)
def test_merge_set_produces_unique_timestamps(
    candles_a: list[Candle], candles_b: list[Candle]
) -> None:
    """After set-merge, each timestamp must appear at most once."""
    table_a = candle_to_table(candles_a, _TS_CONFIG)
    table_b = candle_to_table(candles_b, _TS_CONFIG)
    result = merge_via_set(table_a, table_b, CANDLE_KEY_COLS)
    timestamps = [str(t) for t in result.column("timestamp").to_pylist()]
    assert len(timestamps) == len(set(timestamps))


@given(candle_list(min_size=1, max_size=10), candle_list(min_size=1, max_size=10))
@settings(max_examples=50, deadline=None)
def test_merge_duckdb_produces_unique_timestamps(
    candles_a: list[Candle], candles_b: list[Candle]
) -> None:
    """After DuckDB-merge, each timestamp must appear at most once."""
    table_a = candle_to_table(candles_a, _TS_CONFIG)
    table_b = candle_to_table(candles_b, _TS_CONFIG)
    result = merge_via_duckdb(table_a, table_b, CANDLE_KEY_COLS)
    timestamps = [str(t) for t in result.column("timestamp").to_pylist()]
    assert len(timestamps) == len(set(timestamps))


# ── Merge monotonicity ────────────────────────────────────────────


@given(candle_list(min_size=1, max_size=10), candle_list(min_size=1, max_size=10))
@settings(max_examples=50, deadline=None)
def test_merge_row_count_bounded_by_union_of_keys(
    candles_a: list[Candle], candles_b: list[Candle]
) -> None:
    """Merged row count must equal the number of unique timestamp keys across both inputs."""
    table_a = candle_to_table(candles_a, _TS_CONFIG)
    table_b = candle_to_table(candles_b, _TS_CONFIG)
    unique_keys = {c.timestamp for c in candles_a} | {c.timestamp for c in candles_b}
    result = merge_via_set(table_a, table_b, CANDLE_KEY_COLS)
    assert result.num_rows == len(unique_keys)


# ── Strategy consistency ──────────────────────────────────────────


@given(candle_list(min_size=1, max_size=10), candle_list(min_size=1, max_size=10))
@settings(max_examples=50, deadline=None)
def test_set_and_duckdb_merge_agree_on_row_count(
    candles_a: list[Candle], candles_b: list[Candle]
) -> None:
    """Both merge strategies must produce the same number of rows."""
    table_a = candle_to_table(candles_a, _TS_CONFIG)
    table_b = candle_to_table(candles_b, _TS_CONFIG)
    set_result = merge_via_set(table_a, table_b, CANDLE_KEY_COLS)
    duckdb_result = merge_via_duckdb(table_a, table_b, CANDLE_KEY_COLS)
    assert set_result.num_rows == duckdb_result.num_rows
