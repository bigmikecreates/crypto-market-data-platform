import pyarrow as pa
import pyarrow.parquet as pq

from cmpd.config import TimestampConfig
from cmpd.models.candle import Candle
from cmpd.storage.parquet_writer import (
    _CANDLE_KEY_COLS,
    _merge_tables,
    _merge_via_set,
    _merge_via_duckdb,
    _ROW_MERGE_THRESHOLD,
    write_candles,
)


def _make_candle(
    timestamp: str,
    exchange: str = "fake",
    symbol: str = "BTC-USD",
    timeframe: str = "1h",
    open_str: str = "50000.00",
    high: str = "51000.00",
    low: str = "49000.00",
    close: str = "50500.00",
    volume: str = "100.5",
    source: str = "test",
) -> Candle:
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_str,
        high=high,
        low=low,
        close=close,
        volume=volume,
        source=source,
    )


class TestMergeViaSet:
    def test_identical_rows_are_skipped(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00")
        c2 = _make_candle("2024-01-01T01:00:00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = candle_to_table([c1, c2], ts)
        incoming = candle_to_table([c1], ts)  # same c1, no changes

        result = _merge_via_set(existing, incoming, _CANDLE_KEY_COLS)
        assert result.num_rows == 2
        # return same object when nothing changed
        assert result is existing

    def test_new_rows_are_appended(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00")
        c2 = _make_candle("2024-01-01T01:00:00")
        c3 = _make_candle("2024-01-01T02:00:00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = candle_to_table([c1], ts)
        incoming = candle_to_table([c2, c3], ts)

        result = _merge_via_set(existing, incoming, _CANDLE_KEY_COLS)
        assert result.num_rows == 3

    def test_updated_row_replaces_existing(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00", open_str="100.00")
        c1_updated = _make_candle("2024-01-01T00:00:00", open_str="200.00")
        c2 = _make_candle("2024-01-01T01:00:00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = candle_to_table([c1, c2], ts)
        incoming = candle_to_table([c1_updated], ts)

        result = _merge_via_set(existing, incoming, _CANDLE_KEY_COLS)
        assert result.num_rows == 2
        opens = [str(v) for v in result.column("open").to_pylist()]
        assert "200.0000000000" in opens
        assert opens.count("50000.0000000000") == 1

    def test_mixed_batch(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00", open_str="100.00")
        c2 = _make_candle("2024-01-01T01:00:00", open_str="101.00")
        c2_updated = _make_candle("2024-01-01T01:00:00", open_str="999.00")
        c3 = _make_candle("2024-01-01T02:00:00", open_str="102.00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = candle_to_table([c1, c2], ts)
        incoming = candle_to_table([c2_updated, c3], ts)

        result = _merge_via_set(existing, incoming, _CANDLE_KEY_COLS)
        assert result.num_rows == 3
        opens = sorted(str(v) for v in result.column("open").to_pylist())
        assert opens == ["100.0000000000", "102.0000000000", "999.0000000000"]

    def test_empty_existing_returns_incoming(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = pa.Table.from_pydict({})
        incoming = candle_to_table([c1], ts)

        result = _merge_via_set(existing, incoming, _CANDLE_KEY_COLS)
        assert result.num_rows == 1

    def test_empty_incoming_returns_existing(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = candle_to_table([c1], ts)
        incoming = pa.Table.from_pydict({})

        # An empty incoming table after candle_to_table has 0 rows but may have schema
        result = _merge_via_set(existing, incoming, _CANDLE_KEY_COLS)
        # With empty incoming, existing stays unchanged
        assert result.num_rows == 1


class TestMergeViaDuckDB:
    def test_duckdb_identical_rows(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00")
        c2 = _make_candle("2024-01-01T01:00:00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = candle_to_table([c1, c2], ts)
        incoming = candle_to_table([c1], ts)

        result = _merge_via_duckdb(existing, incoming, _CANDLE_KEY_COLS)
        assert result.num_rows == 2

    def test_duckdb_new_rows_appended(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00")
        c2 = _make_candle("2024-01-01T01:00:00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = candle_to_table([c1], ts)
        incoming = candle_to_table([c2], ts)

        result = _merge_via_duckdb(existing, incoming, _CANDLE_KEY_COLS)
        assert result.num_rows == 2

    def test_duckdb_updated_row(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00", open_str="100.00")
        c1_updated = _make_candle("2024-01-01T00:00:00", open_str="200.00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = candle_to_table([c1], ts)
        incoming = candle_to_table([c1_updated], ts)

        result = _merge_via_duckdb(existing, incoming, _CANDLE_KEY_COLS)
        assert result.num_rows == 1
        opens = [str(v) for v in result.column("open").to_pylist()]
        assert opens == ["200.0000000000"]

    def test_duckdb_updated_row_among_multiple_existing(self) -> None:
        c1 = _make_candle("2024-01-01T00:00:00", open_str="100.00")
        c1_updated = _make_candle("2024-01-01T00:00:00", open_str="200.00")
        c2 = _make_candle("2024-01-01T01:00:00", open_str="101.00")
        ts = TimestampConfig()

        from cmpd.storage.parquet_writer import candle_to_table

        existing = candle_to_table([c1, c2], ts)
        incoming = candle_to_table([c1_updated], ts)

        result = _merge_via_duckdb(existing, incoming, _CANDLE_KEY_COLS)
        assert result.num_rows == 2
        opens = sorted(str(v) for v in result.column("open").to_pylist())
        assert opens == ["101.0000000000", "200.0000000000"]


class TestMergeDispatcher:
    def test_auto_uses_memory_below_threshold(self) -> None:
        table = pa.table({"a": [1]})
        incoming = pa.table({"a": [2]})
        result = _merge_tables(table, incoming, ["a"], strategy="auto")
        # Should use set merge (memory path) for small tables
        assert result.num_rows == 2

    def test_explicit_memory_strategy(self) -> None:
        table = pa.table({"a": [1]})
        incoming = pa.table({"a": [2]})
        result = _merge_tables(table, incoming, ["a"], strategy="memory")
        assert result.num_rows == 2

    def test_explicit_duckdb_strategy(self) -> None:
        table = pa.table({"a": [1]})
        incoming = pa.table({"a": [2]})
        result = _merge_tables(table, incoming, ["a"], strategy="duckdb")
        assert result.num_rows == 2

    def test_threshold_constant_is_reasonable(self) -> None:
        assert _ROW_MERGE_THRESHOLD == 50_000


class TestWriteCandlesMergeEndToEnd:
    def test_second_fetch_same_data_no_duplicates(self, tmp_path) -> None:
        candles = [
            _make_candle("2024-01-01T00:00:00"),
            _make_candle("2024-01-01T01:00:00"),
        ]
        written = write_candles(candles, str(tmp_path))
        assert len(written) == 1
        table = pq.read_table(str(written[0]))
        assert table.num_rows == 2

        written2 = write_candles(candles, str(tmp_path))
        assert len(written2) == 1
        table2 = pq.read_table(str(written2[0]))
        assert table2.num_rows == 2  # no duplicates from re-fetch

    def test_second_fetch_with_correction_updates_row(self, tmp_path) -> None:
        batch_1 = [
            _make_candle("2024-01-01T00:00:00", open_str="100.00"),
        ]
        write_candles(batch_1, str(tmp_path))

        batch_2 = [
            _make_candle("2024-01-01T00:00:00", open_str="200.00"),
        ]
        write_candles(batch_2, str(tmp_path))

        path = tmp_path / "fake" / "BTC-USD" / "1h" / "2024-01-01.parquet"
        table = pq.read_table(str(path))
        assert table.num_rows == 1
        opens = [str(v) for v in table.column("open").to_pylist()]
        assert opens == ["200.0000000000"]

    def test_second_fetch_appends_new_rows(self, tmp_path) -> None:
        c1 = _make_candle("2024-01-01T00:00:00")
        write_candles([c1], str(tmp_path))

        c2 = _make_candle("2024-01-01T01:00:00")
        c3 = _make_candle("2024-01-01T02:00:00")
        write_candles([c2, c3], str(tmp_path))

        path = tmp_path / "fake" / "BTC-USD" / "1h" / "2024-01-01.parquet"
        table = pq.read_table(str(path))
        assert table.num_rows == 3
