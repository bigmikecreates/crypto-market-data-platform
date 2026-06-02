"""Unit tests for Azure helper functions in parquet_writer.

These tests have no dependency on adlfs or Azure credentials and always run
in CI alongside the standard test suite.
"""

import io
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.storage.parquet_writer import (
    backoff,
    is_azure,
    serialize_table,
    strip_azure_scheme,
    uri_for_candle,
    uri_for_funding_rate,
)


# ── is_azure ────────────────────────────────────────────────────────────────


class TestIsAzure:
    def test_az_scheme(self):
        assert is_azure("az://mycontainer/data")

    def test_abfs_scheme(self):
        assert is_azure("abfs://mycontainer/data")

    def test_s3_is_not_azure(self):
        assert not is_azure("s3://bucket/data")

    def test_gs_is_not_azure(self):
        assert not is_azure("gs://bucket/data")

    def test_local_absolute_is_not_azure(self):
        assert not is_azure("/home/user/data")

    def test_local_relative_is_not_azure(self):
        assert not is_azure("data")

    def test_empty_string_is_not_azure(self):
        assert not is_azure("")


# ── strip_azure_scheme ──────────────────────────────────────────────────────


class TestStripAzureScheme:
    def test_strips_az(self):
        assert (
            strip_azure_scheme("az://mycontainer/path/to/file.parquet")
            == "mycontainer/path/to/file.parquet"
        )

    def test_strips_abfs(self):
        assert (
            strip_azure_scheme("abfs://mycontainer/data/sub/file.parquet")
            == "mycontainer/data/sub/file.parquet"
        )

    def test_passthrough_for_non_azure(self):
        assert strip_azure_scheme("local/path.parquet") == "local/path.parquet"

    def test_container_only(self):
        assert strip_azure_scheme("az://mycontainer") == "mycontainer"

    def test_preserves_deep_path(self):
        result = strip_azure_scheme("az://c/exchange/BTC/USDT/1h/2025-01-15.parquet")
        assert result == "c/exchange/BTC/USDT/1h/2025-01-15.parquet"


# ── uri_for_candle ──────────────────────────────────────────────────────────


def _candle(
    ts: str, exchange: str = "kucoin", symbol: str = "BTC-USDT", timeframe: str = "1h"
) -> Candle:
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts,
        open="1",
        high="2",
        low="0",
        close="1",
        volume="10",
        source="test",
    )


class TestUriForCandle:
    def test_basic_uri(self):
        c = _candle("2025-01-15T12:00:00")
        uri = uri_for_candle(c, "az://mycontainer/data")
        assert uri == "az://mycontainer/data/kucoin/BTC-USDT/1h/2025-01-15.parquet"

    def test_date_is_truncated_from_timestamp(self):
        c = _candle("2025-06-30T23:59:59")
        uri = uri_for_candle(c, "az://c/pfx")
        assert uri.endswith("2025-06-30.parquet")

    def test_symbol_slash_preserved(self):
        """BTC/USDT symbols must not be collapsed by Path normalisation."""
        c = _candle("2025-01-01T00:00:00", symbol="BTC/USDT")
        uri = uri_for_candle(c, "az://c/data")
        assert "BTC/USDT" in uri
        # No double-slash outside the scheme (POSIX Path would collapse az:// → az:/)
        without_scheme = uri[len("az://") :]
        assert "//" not in without_scheme

    def test_trailing_slash_on_base_is_normalised(self):
        c = _candle("2025-01-01T00:00:00")
        uri_with = uri_for_candle(c, "az://c/data/")
        uri_without = uri_for_candle(c, "az://c/data")
        assert uri_with == uri_without

    def test_abfs_scheme_preserved(self):
        c = _candle("2025-01-01T00:00:00")
        uri = uri_for_candle(c, "abfs://mycontainer/data")
        assert uri.startswith("abfs://")


# ── uri_for_funding_rate ────────────────────────────────────────────────────


def _rate(ts: str, exchange: str = "bybit", symbol: str = "BTCUSDT") -> FundingRate:
    return FundingRate(
        exchange=exchange,
        symbol=symbol,
        timestamp=ts,
        rate="0.0001",
        predicted_rate="0.0001",
        next_funding_time="2025-01-15T16:00:00",
        source="test",
    )


class TestUriForFundingRate:
    def test_basic_uri(self):
        r = _rate("2025-01-15T08:00:00")
        uri = uri_for_funding_rate(r, "az://c/data")
        assert uri == "az://c/data/bybit/BTCUSDT/funding_rate/2025-01-15.parquet"

    def test_funding_rate_component_present(self):
        r = _rate("2025-03-20T00:00:00")
        uri = uri_for_funding_rate(r, "az://c/data")
        assert "/funding_rate/" in uri

    def test_no_timeframe_component(self):
        r = _rate("2025-01-01T00:00:00")
        uri = uri_for_funding_rate(r, "az://c/data")
        # funding_rate URIs have no timeframe segment
        parts = uri[len("az://") :].split("/")
        assert "funding_rate" in parts
        assert "1h" not in parts


# ── serialize_table ─────────────────────────────────────────────────────────


class TestSerializeTable:
    def test_produces_bytes(self):
        table = pa.table({"x": [1, 2, 3], "y": ["a", "b", "c"]})
        data = serialize_table(table)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_round_trips_through_parquet(self):
        table = pa.table(
            {"x": pa.array([1, 2], type=pa.int64()), "y": ["hello", "world"]}
        )
        data = serialize_table(table)
        recovered = pq.read_table(io.BytesIO(data))
        assert recovered.equals(table)

    def test_preserves_decimal128(self):
        arr = pa.array(["12345.6789"], type=pa.string()).cast(pa.decimal128(38, 10))
        table = pa.table({"price": arr})
        data = serialize_table(table)
        recovered = pq.read_table(io.BytesIO(data))
        assert recovered.schema.field("price").type == pa.decimal128(38, 10)
        assert recovered.column("price")[0].as_py() == table.column("price")[0].as_py()

    def test_empty_table_produces_valid_parquet(self):
        table = pa.table({"x": pa.array([], type=pa.int64())})
        data = serialize_table(table)
        recovered = pq.read_table(io.BytesIO(data))
        assert recovered.num_rows == 0


# ── backoff ─────────────────────────────────────────────────────────────────


class TestBackoff:
    @patch("crmd_platform.storage.parquet_writer.time.sleep")
    @patch("crmd_platform.storage.parquet_writer.random.uniform", return_value=0.0)
    def test_attempt_0_sleeps_half_second(self, _mock_uniform, mock_sleep):
        backoff(0)
        mock_sleep.assert_called_once()
        duration = mock_sleep.call_args[0][0]
        assert 0.5 <= duration < 1.0

    @patch("crmd_platform.storage.parquet_writer.time.sleep")
    @patch("crmd_platform.storage.parquet_writer.random.uniform", return_value=0.0)
    def test_duration_doubles_each_attempt(self, _mock_uniform, mock_sleep):
        durations = []
        for attempt in range(4):
            backoff(attempt)
            durations.append(mock_sleep.call_args[0][0])
        # 0.5, 1.0, 2.0, 4.0 (without jitter)
        assert durations[1] == pytest.approx(durations[0] * 2, abs=0.01)
        assert durations[2] == pytest.approx(durations[1] * 2, abs=0.01)
        assert durations[3] == pytest.approx(durations[2] * 2, abs=0.01)

    @patch("crmd_platform.storage.parquet_writer.time.sleep")
    @patch("crmd_platform.storage.parquet_writer.random.uniform", return_value=0.0)
    def test_capped_at_eight_seconds(self, _mock_uniform, mock_sleep):
        backoff(100)
        duration = mock_sleep.call_args[0][0]
        assert duration == pytest.approx(8.0, abs=0.01)

    @patch("crmd_platform.storage.parquet_writer.time.sleep")
    def test_jitter_adds_up_to_half_second(self, mock_sleep):
        # Run many times and check the jitter range
        for _ in range(50):
            backoff(0)
        durations = [call[0][0] for call in mock_sleep.call_args_list]
        assert all(0.5 <= d < 1.1 for d in durations)
