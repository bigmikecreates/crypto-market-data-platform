from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from crmd_platform.utils.parquet_viewer import (
    discover_files,
    format_table,
    get_column_stats,
    get_metadata_info,
    get_schema_info,
    parse_timestamp,
    read_and_filter,
    run_inspect,
    table_to_dicts,
)

_START_TS = 1704067200  # 2024-01-01T00:00:00 UTC


def _make_candle_table(
    n_rows: int, start_ts: int = _START_TS, interval_s: int = 3600
) -> pa.Table:
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []
    ts_vals = []
    exchanges = []
    symbols = []
    timeframes = []
    sources = []

    for i in range(n_rows):
        ts = start_ts + i * interval_s
        ts_vals.append(ts)
        opens.append(f"{100 + i}.0")
        highs.append(f"{110 + i}.0")
        lows.append(f"{90 + i}.0")
        closes.append(f"{105 + i}.0")
        volumes.append(f"{10 + i}.0")
        exchanges.append("test_exchange")
        symbols.append("TEST/SYMBOL")
        timeframes.append("1h")
        sources.append("test")

    return pa.table(
        {
            "exchange": pa.array(exchanges, type=pa.string()),
            "symbol": pa.array(symbols, type=pa.string()),
            "timeframe": pa.array(timeframes, type=pa.string()),
            "timestamp": pa.array(ts_vals, type=pa.timestamp("s")),
            "open": pa.array(opens, type=pa.string()).cast(pa.decimal128(38, 10)),
            "high": pa.array(highs, type=pa.string()).cast(pa.decimal128(38, 10)),
            "low": pa.array(lows, type=pa.string()).cast(pa.decimal128(38, 10)),
            "close": pa.array(closes, type=pa.string()).cast(pa.decimal128(38, 10)),
            "volume": pa.array(volumes, type=pa.string()).cast(pa.decimal128(38, 10)),
            "source": pa.array(sources, type=pa.string()),
        }
    )


def _write_table(table: pa.Table, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, str(path))
    return path


# ── parse_timestamp ─────────────────────────────────────────────────


class TestParseTimestamp:
    def test_full_iso(self) -> None:
        ts = parse_timestamp("2024-01-01T00:00:00")
        assert ts == _START_TS

    def test_date_only(self) -> None:
        ts = parse_timestamp("2024-01-01")
        assert ts == _START_TS

    def test_midday(self) -> None:
        ts = parse_timestamp("2024-01-01T12:00:00")
        assert ts == _START_TS + 43200

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Unable to parse timestamp"):
            parse_timestamp("not-a-date")


# ── discover_files ──────────────────────────────────────────────────


class TestDiscoverFiles:
    def test_single_file(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(5), tmp_path / "data.parquet")
        files = discover_files(str(p))
        assert files == [p]

    def test_directory(self, tmp_path: Path) -> None:
        _write_table(_make_candle_table(5), tmp_path / "a.parquet")
        _write_table(_make_candle_table(5), tmp_path / "b.parquet")
        files = discover_files(str(tmp_path))
        assert len(files) == 2

    def test_nonexistent(self) -> None:
        with pytest.raises(FileNotFoundError, match="Path does not exist"):
            discover_files("/nonexistent/path.parquet")

    def test_no_parquet_files(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("hello")
        with pytest.raises(ValueError, match="No parquet files found"):
            discover_files(str(tmp_path))

    def test_non_parquet_file(self, tmp_path: Path) -> None:
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3")
        with pytest.raises(ValueError, match="Not a parquet file"):
            discover_files(str(f))

    def test_relative_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_table(_make_candle_table(3), Path("data.parquet"))
        files = discover_files("data.parquet")
        assert len(files) == 1
        assert files[0].name == "data.parquet"


# ── read_and_filter ─────────────────────────────────────────────────


class TestReadAndFilter:
    def test_no_range_returns_all(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        table = read_and_filter([p], None, None)
        assert len(table) == 24

    def test_range_filters_correctly(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        table = read_and_filter([p], _START_TS, _START_TS + 7200)
        assert len(table) == 2

    def test_range_excludes_end_boundary(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        table = read_and_filter([p], _START_TS, _START_TS + 3600)
        assert len(table) == 1

    def test_multiple_files(self, tmp_path: Path) -> None:
        t1 = _make_candle_table(10, start_ts=_START_TS)
        t2 = _make_candle_table(10, start_ts=_START_TS + 36000)
        p1 = _write_table(t1, tmp_path / "a.parquet")
        p2 = _write_table(t2, tmp_path / "b.parquet")
        table = read_and_filter([p1, p2], None, None)
        assert len(table) == 20

    def test_range_on_multiple_files(self, tmp_path: Path) -> None:
        t1 = _make_candle_table(10, start_ts=_START_TS)
        t2 = _make_candle_table(10, start_ts=_START_TS + 36000)
        p1 = _write_table(t1, tmp_path / "a.parquet")
        p2 = _write_table(t2, tmp_path / "b.parquet")
        table = read_and_filter([p1, p2], _START_TS + 3600 * 8, _START_TS + 3600 * 12)
        assert len(table) == 4


# ── get_schema_info ─────────────────────────────────────────────────


class TestGetSchemaInfo:
    def test_column_names(self) -> None:
        table = _make_candle_table(1)
        info = get_schema_info(table)
        names = [n for n, _ in info]
        assert names == [
            "exchange",
            "symbol",
            "timeframe",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "source",
        ]

    def test_decimal_types(self) -> None:
        table = _make_candle_table(1)
        info = get_schema_info(table)
        for name, typ in info:
            if name in ("open", "high", "low", "close", "volume"):
                assert "decimal128" in typ


# ── get_column_stats ────────────────────────────────────────────────


class TestGetColumnStats:
    def test_decimal_columns_have_min_max(self) -> None:
        table = _make_candle_table(5)
        stats = get_column_stats(table)
        open_stats = next(s for s in stats if s["name"] == "open")
        assert "min" in open_stats
        assert "max" in open_stats
        assert open_stats["min"] == "100.0000000000"
        assert open_stats["max"] == "104.0000000000"

    def test_string_columns_have_no_min_max(self) -> None:
        table = _make_candle_table(5)
        stats = get_column_stats(table)
        exchange_stats = next(s for s in stats if s["name"] == "exchange")
        assert "min" not in exchange_stats
        assert "max" not in exchange_stats

    def test_null_counts(self) -> None:
        table = _make_candle_table(5)
        stats = get_column_stats(table)
        for s in stats:
            assert s["nulls"] == 0


# ── get_metadata_info ───────────────────────────────────────────────


class TestGetMetadataInfo:
    def test_metadata_shape(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        meta = get_metadata_info(p)
        assert meta["rows"] == 24
        assert meta["columns"] == 10
        assert meta["row_groups"] >= 1
        assert meta["created_by"] != "unknown"

    def test_row_group_details(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(100), tmp_path / "data.parquet")
        meta = get_metadata_info(p)
        assert len(meta["row_group_details"]) >= 1
        first = meta["row_group_details"][0]
        assert "rows" in first
        assert "total_byte_size" in first
        assert "compression" in first


# ── table_to_dicts ──────────────────────────────────────────────────


class TestTableToDicts:
    def test_converts_columns(self) -> None:
        table = _make_candle_table(3)
        rows = table_to_dicts(table, limit=10)
        assert len(rows) == 3
        assert rows[0]["exchange"] == "test_exchange"
        assert rows[0]["symbol"] == "TEST/SYMBOL"

    def test_timestamp_format(self) -> None:
        table = _make_candle_table(1)
        rows = table_to_dicts(table, limit=10)
        assert rows[0]["timestamp"] == "2024-01-01T00:00:00"

    def test_limit(self) -> None:
        table = _make_candle_table(24)
        rows = table_to_dicts(table, limit=5)
        assert len(rows) == 5

    def test_decimal_values_as_strings(self) -> None:
        table = _make_candle_table(1)
        rows = table_to_dicts(table, limit=10)
        assert rows[0]["open"] == "100"
        assert rows[0]["high"] == "110"
        assert rows[0]["low"] == "90"
        assert rows[0]["close"] == "105"
        assert rows[0]["volume"] == "10"


# ── format_table ────────────────────────────────────────────────────


class TestFormatTable:
    def test_empty_rows(self) -> None:
        assert format_table([], columns=["a"]) == "  (no rows)"

    def test_header_and_separator(self) -> None:
        rows = [{"col": "val"}]
        output = format_table(rows)
        assert "col" in output
        assert "─" in output
        assert "val" in output

    def test_multiple_columns(self) -> None:
        rows = [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
        output = format_table(rows)
        assert "a" in output
        assert "b" in output
        assert "1" in output
        assert "3" in output

    def test_custom_column_order(self) -> None:
        rows = [{"a": "1", "b": "2"}]
        output = format_table(rows, columns=["b", "a"])
        lines = output.strip().split("\n")
        assert lines[0].strip().startswith("b")


# ── run_inspect integration ─────────────────────────────────────────


class TestRunInspect:
    def test_default_output(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        result = run_inspect(str(p))
        assert "File:" in result
        assert "Rows: 24" in result
        assert "Schema:" in result
        assert "Sample (first 10):" in result
        assert "exchange" in result
        assert "decimal128" in result

    def test_limit(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        result = run_inspect(str(p), limit=5)
        assert "Sample (first 5):" in result

    def test_with_stats(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        result = run_inspect(str(p), show_stats=True)
        assert "Statistics:" in result
        assert "min=" in result
        assert "max=" in result
        assert "nulls=" in result

    def test_with_range(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        result = run_inspect(str(p), start="2024-01-01", end="2024-01-01T03:00:00")
        assert "Rows: 3" in result

    def test_range_excludes_end_boundary(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        result = run_inspect(
            str(p), start="2024-01-01T00:00:00", end="2024-01-01T01:00:00"
        )
        assert "Rows: 1" in result

    def test_start_only(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        result = run_inspect(str(p), start="2024-01-01T12:00:00")
        assert "Rows: 12" in result

    def test_end_only(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        result = run_inspect(str(p), end="2024-01-01T06:00:00")
        assert "Rows: 6" in result

    def test_directory(self, tmp_path: Path) -> None:
        _write_table(_make_candle_table(10), tmp_path / "a.parquet")
        _write_table(_make_candle_table(14), tmp_path / "b.parquet")
        result = run_inspect(str(tmp_path))
        assert "Directory:" in result
        assert "Files: 2" in result
        assert "Rows: 24" in result

    def test_directory_with_range(self, tmp_path: Path) -> None:
        t1 = _make_candle_table(10, start_ts=_START_TS)
        t2 = _make_candle_table(10, start_ts=_START_TS + 36000)
        _write_table(t1, tmp_path / "a.parquet")
        _write_table(t2, tmp_path / "b.parquet")
        result = run_inspect(
            str(tmp_path), start="2024-01-01T06:00:00", end="2024-01-01T14:00:00"
        )
        assert "Rows: 8" in result

    def test_verbose_single_file(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(24), tmp_path / "data.parquet")
        result = run_inspect(str(p), show_verbose=True)
        assert "Metadata:" in result
        assert "Row groups:" in result
        assert "Created by:" in result

    def test_verbose_directory_omits_metadata(self, tmp_path: Path) -> None:
        _write_table(_make_candle_table(5), tmp_path / "a.parquet")
        _write_table(_make_candle_table(5), tmp_path / "b.parquet")
        result = run_inspect(str(tmp_path), show_verbose=True)
        assert "Metadata:" not in result

    def test_relative_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_table(_make_candle_table(8), Path("data.parquet"))
        result = run_inspect("data.parquet")
        assert "Rows: 8" in result

    def test_empty_after_filter(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(5), tmp_path / "data.parquet")
        result = run_inspect(str(p), start="2025-01-01", end="2025-01-02")
        assert "Rows: 0" in result
        assert "Sample (first 0):" in result

    def test_invalid_path_error(self) -> None:
        with pytest.raises(SystemExit):
            # Simulate the CLI error path
            try:
                run_inspect("/nonexistent/path.parquet")
            except FileNotFoundError:
                raise SystemExit(1)

    def test_invalid_timestamp_error(self, tmp_path: Path) -> None:
        p = _write_table(_make_candle_table(5), tmp_path / "data.parquet")
        with pytest.raises(ValueError, match="Unable to parse timestamp"):
            run_inspect(str(p), start="bad-date")
