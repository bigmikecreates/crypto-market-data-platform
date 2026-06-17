import pyarrow.parquet as pq

from crmd_platform.config import TimestampConfig
from crmd_platform.storage import create_backend
from crmd_platform.storage.parquet_writer import (
    write_candles,
)
from tests.conftest import make_candle as _make_candle


class TestWriteCandlesPartitioning:
    def test_same_date_no_duplicates(self, tmp_path) -> None:
        candles = [
            _make_candle("2024-01-01T00:00:00"),
            _make_candle("2024-01-01T01:00:00"),
            _make_candle("2024-01-01T02:00:00"),
        ]
        written = write_candles(
            candles, str(tmp_path), backend=create_backend(str(tmp_path))
        )
        assert len(written) == 1

        table = pq.read_table(str(written[0]))
        assert table.num_rows == 3

        timestamps = [
            str(t).split(" ")[0] for t in table.column("timestamp").to_pylist()
        ]
        assert timestamps == ["2024-01-01", "2024-01-01", "2024-01-01"]

    def test_multiple_dates_correct_partitions(self, tmp_path) -> None:
        candles = [
            _make_candle("2024-01-01T23:00:00"),
            _make_candle("2024-01-02T00:00:00"),
            _make_candle("2024-01-02T01:00:00"),
        ]
        written = write_candles(
            candles, str(tmp_path), backend=create_backend(str(tmp_path))
        )
        assert len(written) == 2

        paths_by_date = {p.name: p for p in written}
        assert "2024-01-01.parquet" in paths_by_date
        assert "2024-01-02.parquet" in paths_by_date

        day1 = pq.read_table(str(paths_by_date["2024-01-01.parquet"]))
        assert day1.num_rows == 1
        ts_1 = str(day1.column("timestamp").to_pylist()[0]).split(" ")[0]
        assert ts_1 == "2024-01-01"

        day2 = pq.read_table(str(paths_by_date["2024-01-02.parquet"]))
        assert day2.num_rows == 2
        for t in day2.column("timestamp").to_pylist():
            date_str = str(t).split(" ")[0]
            assert date_str == "2024-01-02"

    def test_no_row_in_wrong_partition(self, tmp_path) -> None:
        candles = [
            _make_candle("2024-06-01T23:00:00"),
            _make_candle("2024-06-02T00:00:00"),
        ]
        written = write_candles(
            candles, str(tmp_path), backend=create_backend(str(tmp_path))
        )
        assert len(written) == 2

        paths_by_date = {p.name: p for p in written}

        day1 = pq.read_table(str(paths_by_date["2024-06-01.parquet"]))
        day1_ts = day1.column("timestamp").to_pylist()
        assert len(day1_ts) == 1
        assert "2024-06-01" in str(day1_ts[0])
        assert "2024-06-02" not in str(day1_ts[0])

        day2 = pq.read_table(str(paths_by_date["2024-06-02.parquet"]))
        day2_ts = day2.column("timestamp").to_pylist()
        assert len(day2_ts) == 1
        assert "2024-06-02" in str(day2_ts[0])
        assert "2024-06-01" not in str(day2_ts[0])

    def test_append_no_duplicate_from_existing(self, tmp_path) -> None:
        batch_1 = [
            _make_candle("2024-03-01T00:00:00", open_str="100.00"),
            _make_candle("2024-03-01T01:00:00", open_str="101.00"),
        ]
        write_candles(batch_1, str(tmp_path), backend=create_backend(str(tmp_path)))

        batch_2 = [
            _make_candle("2024-03-01T02:00:00", open_str="102.00"),
            _make_candle("2024-03-02T00:00:00", open_str="200.00"),
        ]
        write_candles(batch_2, str(tmp_path), backend=create_backend(str(tmp_path)))

        path_d1 = str(tmp_path / "fake" / "BTC-USD" / "1h" / "2024-03-01.parquet")
        path_d2 = str(tmp_path / "fake" / "BTC-USD" / "1h" / "2024-03-02.parquet")

        day1 = pq.read_table(path_d1)
        assert day1.num_rows == 3

        day2 = pq.read_table(path_d2)
        assert day2.num_rows == 1

        opens = sorted(day1.column("open").to_pylist())
        assert opens == [100.00, 101.00, 102.00]


class TestWriteCandlesEdgeCases:
    def test_empty_list_returns_empty(self, tmp_path) -> None:
        result = write_candles([], str(tmp_path))
        assert result == []

    def test_default_base_path(self, tmp_path) -> None:
        ts_config = TimestampConfig()
        candles = [_make_candle("2024-01-01T00:00:00")]
        result = write_candles(
            candles,
            base_path=tmp_path,
            backend=create_backend(str(tmp_path)),
            ts_config=ts_config,
        )
        expected = tmp_path / "fake" / "BTC-USD" / "1h" / "2024-01-01.parquet"
        assert result[0] == expected

    def test_mixed_exchanges_symbols_timeframes(self, tmp_path) -> None:
        c1 = _make_candle(
            "2024-01-01T00:00:00", exchange="a", symbol="X", timeframe="1h"
        )
        c2 = _make_candle(
            "2024-01-01T00:00:00", exchange="b", symbol="Y", timeframe="1d"
        )
        written = write_candles(
            [c1, c2], str(tmp_path), backend=create_backend(str(tmp_path))
        )
        assert len(written) == 2
