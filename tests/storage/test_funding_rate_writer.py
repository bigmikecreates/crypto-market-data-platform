import shutil
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from crmd_platform.config import TimestampConfig
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.storage.parquet_writer import (
    funding_rate_to_table,
    write_funding_rates,
)


def _fr(**overrides) -> FundingRate:
    fields = dict(
        exchange="test_exchange",
        symbol="PI_XBTUSD",
        timestamp="2024-01-01T12:00:00",
        rate="0.0001",
        predicted_rate="0.0002",
        next_funding_time="2024-01-01T16:00:00",
        source="test_provider",
    )
    fields.update(overrides)
    return FundingRate(**fields)


def _ts_config(resolution: str = "s") -> TimestampConfig:
    return TimestampConfig(resolution=resolution)


# -- funding_rate_to_table -------------------------------------


class TestFundingRateToTable:
    def test_empty_returns_empty_table(self):
        table = funding_rate_to_table([], _ts_config())
        assert table.num_rows == 0

    def test_single_rate(self):
        r = _fr()
        table = funding_rate_to_table([r], _ts_config())
        assert table.num_rows == 1
        assert table.schema.field("rate").type == pa.decimal128(38, 10)
        assert table.schema.field("predicted_rate").type == pa.decimal128(38, 10)
        assert table.schema.field("timestamp").type == pa.timestamp("s")
        assert table.schema.field("next_funding_time").type == pa.timestamp("s")

    def test_multiple_rates_have_correct_values(self):
        rates = [
            _fr(timestamp="2024-01-01T12:00:00", rate="0.0001"),
            _fr(timestamp="2024-01-01T16:00:00", rate="-0.0002"),
        ]
        table = funding_rate_to_table(rates, _ts_config())
        assert table.num_rows == 2
        assert str(table.column("rate")[0].as_py()) == "0.0001000000"
        assert str(table.column("rate")[1].as_py()) == "-0.0002000000"

    def test_column_names(self):
        r = _fr()
        table = funding_rate_to_table([r], _ts_config())
        names = table.schema.names
        assert names == [
            "exchange",
            "symbol",
            "timestamp",
            "rate",
            "predicted_rate",
            "next_funding_time",
            "source",
        ]


# -- write_funding_rates ---------------------------------------


class TestWriteFundingRates:
    @pytest.fixture(autouse=True)
    def _tmpdir(self):
        tmp = tempfile.mkdtemp()
        yield tmp
        shutil.rmtree(tmp)

    def test_same_date_no_duplicates(self, _tmpdir):
        rates = [
            _fr(timestamp="2024-01-01T12:00:00"),
            _fr(timestamp="2024-01-01T16:00:00"),
        ]
        written = write_funding_rates(rates, base_path=_tmpdir)
        assert len(written) == 1

        table = pq.read_table(str(written[0]))
        assert table.num_rows == 2

    def test_multiple_dates_correct_partitions(self, _tmpdir):
        rates = [
            _fr(timestamp="2024-01-01T12:00:00"),
            _fr(timestamp="2024-01-02T12:00:00"),
        ]
        written = write_funding_rates(rates, base_path=_tmpdir)
        assert len(written) == 2

        table1 = pq.read_table(str(written[0]))
        table2 = pq.read_table(str(written[1]))
        assert table1.num_rows == 1
        assert table2.num_rows == 1
        written_names = {str(p).split("/")[-1] for p in written}
        assert written_names == {"2024-01-01.parquet", "2024-01-02.parquet"}

    def test_empty_list_returns_empty(self, _tmpdir):
        written = write_funding_rates([], base_path=_tmpdir)
        assert written == []

    def test_default_base_path(self, _tmpdir):
        rates = [_fr(timestamp="2024-01-01T12:00:00")]

        # use _tmpdir as base_path; default_base_path test checks "data/"
        written = write_funding_rates(rates, base_path=_tmpdir)
        assert len(written) == 1
        assert written[0].exists()

    def test_mixed_exchanges_symbols_separate_paths(self, _tmpdir):
        rates = [
            _fr(exchange="ex_a", symbol="PI_XBTUSD", timestamp="2024-01-01T12:00:00"),
            _fr(exchange="ex_b", symbol="PI_ETHUSD", timestamp="2024-01-01T12:00:00"),
        ]
        written = write_funding_rates(rates, base_path=_tmpdir)
        assert len(written) == 2
        assert str(written[0]) != str(written[1])

    def test_append_no_duplicates(self, _tmpdir):
        r = _fr(timestamp="2024-01-01T12:00:00")
        write_funding_rates([r], base_path=_tmpdir)
        write_funding_rates([r], base_path=_tmpdir)

        table = pq.read_table(
            str(
                Path(_tmpdir)
                / "test_exchange"
                / "PI_XBTUSD"
                / "funding_rate"
                / "2024-01-01.parquet"
            )
        )
        assert table.num_rows == 1  # identical row was skipped

    def test_append_new_rows(self, _tmpdir):
        r1 = _fr(timestamp="2024-01-01T12:00:00")
        r2 = _fr(timestamp="2024-01-01T16:00:00")
        write_funding_rates([r1], base_path=_tmpdir)
        write_funding_rates([r2], base_path=_tmpdir)

        table = pq.read_table(
            str(
                Path(_tmpdir)
                / "test_exchange"
                / "PI_XBTUSD"
                / "funding_rate"
                / "2024-01-01.parquet"
            )
        )
        assert table.num_rows == 2  # new row was appended
