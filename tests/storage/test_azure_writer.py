"""Mock-based unit tests for azure_lease_write and the Azure branches of
write_candles / write_funding_rates.

Requires adlfs (and therefore azure-core) so that HttpResponseError is
importable. The module is skipped automatically when adlfs is not installed.
"""

import io
from unittest.mock import MagicMock, call, patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

adlfs = pytest.importorskip("adlfs", reason="adlfs not installed")
from azure.core.exceptions import HttpResponseError  # noqa: E402

from crmd_platform.models.candle import Candle  # noqa: E402
from crmd_platform.models.funding_rate import FundingRate  # noqa: E402
from crmd_platform.storage.parquet_writer import (  # noqa: E402
    azure_lease_write,
    write_candles,
    write_funding_rates,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _http_409() -> HttpResponseError:
    e = HttpResponseError()
    e.status_code = 409
    return e


def _http_500() -> HttpResponseError:
    e = HttpResponseError()
    e.status_code = 500
    return e


@pytest.fixture
def mock_fs():
    return MagicMock()


@pytest.fixture
def mock_blob_client(mock_fs):
    client = MagicMock()
    mock_fs.service_client.get_blob_client.return_value = client
    return client


@pytest.fixture
def minimal_table():
    """A simple two-column table used as stand-in for both existing and incoming data."""
    return pa.table({"k": [1], "v": ["hello"]})


@pytest.fixture
def candles():
    return [
        Candle(
            exchange="kucoin", symbol="BTC-USDT", timeframe="1h",
            timestamp="2025-01-15T00:00:00",
            open="50000", high="51000", low="49000", close="50500",
            volume="10", source="test",
        )
    ]


@pytest.fixture
def rates():
    return [
        FundingRate(
            exchange="bybit", symbol="BTCUSDT",
            timestamp="2025-01-15T08:00:00",
            rate="0.0001", predicted_rate="0.0001",
            next_funding_time="2025-01-15T16:00:00",
            source="test",
        )
    ]


# ── New blob: success on first attempt ───────────────────────────────────────


class TestNewBlob:
    @patch("crmd_platform.storage.parquet_writer.backoff")
    def test_uploads_without_overwrite(self, mock_backoff, mock_fs, mock_blob_client, minimal_table):
        mock_fs.exists.return_value = False

        azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        mock_blob_client.upload_blob.assert_called_once()
        kwargs = mock_blob_client.upload_blob.call_args.kwargs
        assert kwargs["overwrite"] is False
        mock_backoff.assert_not_called()

    @patch("crmd_platform.storage.parquet_writer.backoff")
    def test_does_not_acquire_lease_for_new_blob(
        self, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        mock_fs.exists.return_value = False

        azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        mock_blob_client.acquire_lease.assert_not_called()

    @patch("crmd_platform.storage.parquet_writer.backoff")
    def test_new_blob_409_retries_via_lease_path(
        self, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        """A 409 on the conditional PUT means another worker created the blob; we
        should fall through to the lease path on the next loop iteration."""
        lease = MagicMock()
        mock_fs.exists.side_effect = [False, True]
        mock_blob_client.upload_blob.side_effect = [_http_409(), None]
        mock_blob_client.acquire_lease.return_value = lease

        with patch("crmd_platform.storage.parquet_writer.pq.read_table", return_value=minimal_table):
            azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        assert mock_blob_client.upload_blob.call_count == 2
        # Second call must carry the lease
        second_call_kwargs = mock_blob_client.upload_blob.call_args_list[1].kwargs
        assert second_call_kwargs["overwrite"] is True
        assert second_call_kwargs["lease"] == lease


# ── Existing blob: lease acquired successfully ────────────────────────────────


class TestExistingBlob:
    @patch("crmd_platform.storage.parquet_writer.backoff")
    @patch("crmd_platform.storage.parquet_writer.pq.read_table")
    def test_acquires_lease_with_30s_duration(
        self, mock_read, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        mock_fs.exists.return_value = True
        mock_read.return_value = minimal_table
        mock_blob_client.acquire_lease.return_value = MagicMock()

        azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        mock_blob_client.acquire_lease.assert_called_once_with(lease_duration=30)

    @patch("crmd_platform.storage.parquet_writer.backoff")
    @patch("crmd_platform.storage.parquet_writer.pq.read_table")
    def test_reads_existing_blob_with_filesystem(
        self, mock_read, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        mock_fs.exists.return_value = True
        mock_read.return_value = minimal_table
        mock_blob_client.acquire_lease.return_value = MagicMock()

        azure_lease_write(minimal_table, "c/path/file.parquet", mock_fs, ["k"], "auto")

        mock_read.assert_called_once_with("c/path/file.parquet", filesystem=mock_fs)

    @patch("crmd_platform.storage.parquet_writer.backoff")
    @patch("crmd_platform.storage.parquet_writer.pq.read_table")
    def test_uploads_merged_bytes_with_lease(
        self, mock_read, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        lease = MagicMock()
        mock_fs.exists.return_value = True
        mock_read.return_value = minimal_table
        mock_blob_client.acquire_lease.return_value = lease

        azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        mock_blob_client.upload_blob.assert_called_once()
        kwargs = mock_blob_client.upload_blob.call_args.kwargs
        assert kwargs["overwrite"] is True
        assert kwargs["lease"] is lease
        # The data must be Parquet bytes
        data = mock_blob_client.upload_blob.call_args.args[0]
        recovered = pq.read_table(io.BytesIO(data))
        assert recovered.num_rows == 1

    @patch("crmd_platform.storage.parquet_writer.backoff")
    @patch("crmd_platform.storage.parquet_writer.pq.read_table")
    def test_releases_lease_on_success(
        self, mock_read, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        lease = MagicMock()
        mock_fs.exists.return_value = True
        mock_read.return_value = minimal_table
        mock_blob_client.acquire_lease.return_value = lease

        azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        lease.release.assert_called_once()

    @patch("crmd_platform.storage.parquet_writer.backoff")
    @patch("crmd_platform.storage.parquet_writer.pq.read_table")
    def test_releases_lease_when_merge_raises(
        self, mock_read, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        """The finally block must release the lease even if _merge_tables blows up."""
        lease = MagicMock()
        mock_fs.exists.return_value = True
        mock_read.side_effect = RuntimeError("simulated read failure")
        mock_blob_client.acquire_lease.return_value = lease

        with pytest.raises(RuntimeError, match="simulated read failure"):
            azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        lease.release.assert_called_once()

    @patch("crmd_platform.storage.parquet_writer.backoff")
    @patch("crmd_platform.storage.parquet_writer.pq.read_table")
    def test_non_409_error_on_upload_is_reraised(
        self, mock_read, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        lease = MagicMock()
        mock_fs.exists.return_value = True
        mock_read.return_value = minimal_table
        mock_blob_client.acquire_lease.return_value = lease
        mock_blob_client.upload_blob.side_effect = _http_500()

        with pytest.raises(HttpResponseError) as exc_info:
            azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        assert exc_info.value.status_code == 500
        lease.release.assert_called_once()


# ── Lease contention: 409 on acquire_lease ───────────────────────────────────


class TestLeaseContention:
    @patch("crmd_platform.storage.parquet_writer.backoff")
    @patch("crmd_platform.storage.parquet_writer.pq.read_table")
    def test_retries_on_lease_409(
        self, mock_read, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        lease = MagicMock()
        mock_fs.exists.return_value = True
        mock_blob_client.acquire_lease.side_effect = [_http_409(), _http_409(), lease]
        mock_read.return_value = minimal_table

        azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        assert mock_blob_client.acquire_lease.call_count == 3
        assert mock_backoff.call_count == 2

    @patch("crmd_platform.storage.parquet_writer.backoff")
    def test_max_attempts_raises_runtime_error(
        self, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        mock_fs.exists.return_value = True
        mock_blob_client.acquire_lease.side_effect = _http_409()

        with pytest.raises(RuntimeError, match="after 6 attempts"):
            azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        assert mock_blob_client.acquire_lease.call_count == 6

    @patch("crmd_platform.storage.parquet_writer.backoff")
    def test_non_409_on_acquire_is_reraised_immediately(
        self, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        mock_fs.exists.return_value = True
        mock_blob_client.acquire_lease.side_effect = _http_500()

        with pytest.raises(HttpResponseError) as exc_info:
            azure_lease_write(minimal_table, "c/file.parquet", mock_fs, ["k"], "auto")

        assert exc_info.value.status_code == 500
        # Should not retry on non-transient errors
        assert mock_blob_client.acquire_lease.call_count == 1
        mock_backoff.assert_not_called()

    @patch("crmd_platform.storage.parquet_writer.backoff")
    def test_backoff_called_with_incrementing_attempt_number(
        self, mock_backoff, mock_fs, mock_blob_client, minimal_table
    ):
        mock_fs.exists.return_value = True
        mock_blob_client.acquire_lease.side_effect = _http_409()

        with pytest.raises(RuntimeError):
            azure_lease_write(
                minimal_table, "c/file.parquet", mock_fs, ["k"], "auto", max_attempts=3
            )

        assert mock_backoff.call_count == 3
        assert mock_backoff.call_args_list == [call(0), call(1), call(2)]


# ── write_candles with Azure base_path ───────────────────────────────────────


class TestWriteCandlesAzure:
    @patch("crmd_platform.storage.parquet_writer.azure_lease_write")
    @patch("crmd_platform.storage.parquet_writer.azure_filesystem")
    def test_routes_to_lease_write(self, mock_fs_factory, mock_lease_write, candles):
        mock_fs = MagicMock()
        mock_fs_factory.return_value = mock_fs
        mock_fs.exists.return_value = False

        result = write_candles(candles, base_path="az://c/data")

        mock_lease_write.assert_called_once()
        assert len(result) == 1

    @patch("crmd_platform.storage.parquet_writer.azure_lease_write")
    @patch("crmd_platform.storage.parquet_writer.azure_filesystem")
    def test_returns_full_uris(self, mock_fs_factory, mock_lease_write, candles):
        mock_fs_factory.return_value = MagicMock()

        result = write_candles(candles, base_path="az://c/data")

        assert len(result) == 1
        assert str(result[0]).startswith("az://")

    @patch("crmd_platform.storage.parquet_writer.azure_lease_write")
    @patch("crmd_platform.storage.parquet_writer.azure_filesystem")
    def test_blob_path_passed_to_lease_write(self, mock_fs_factory, mock_lease_write, candles):
        mock_fs_factory.return_value = MagicMock()

        write_candles(candles, base_path="az://mycontainer/data")

        blob_path_arg = mock_lease_write.call_args.args[1]
        # blob_path is strip_azure_scheme(uri) — no az:// prefix
        assert not blob_path_arg.startswith("az://")
        assert blob_path_arg.startswith("mycontainer/")

    @patch("crmd_platform.storage.parquet_writer.azure_lease_write")
    @patch("crmd_platform.storage.parquet_writer.azure_filesystem")
    def test_empty_candles_returns_empty(self, mock_fs_factory, mock_lease_write):
        result = write_candles([], base_path="az://c/data")
        assert result == []
        mock_lease_write.assert_not_called()


# ── write_funding_rates with Azure base_path ─────────────────────────────────


class TestWriteFundingRatesAzure:
    @patch("crmd_platform.storage.parquet_writer.azure_lease_write")
    @patch("crmd_platform.storage.parquet_writer.azure_filesystem")
    def test_routes_to_lease_write(self, mock_fs_factory, mock_lease_write, rates):
        mock_fs_factory.return_value = MagicMock()

        result = write_funding_rates(rates, base_path="az://c/data")

        mock_lease_write.assert_called_once()
        assert len(result) == 1

    @patch("crmd_platform.storage.parquet_writer.azure_lease_write")
    @patch("crmd_platform.storage.parquet_writer.azure_filesystem")
    def test_uri_contains_funding_rate_segment(self, mock_fs_factory, mock_lease_write, rates):
        mock_fs_factory.return_value = MagicMock()

        result = write_funding_rates(rates, base_path="az://c/data")

        assert "funding_rate" in str(result[0])
