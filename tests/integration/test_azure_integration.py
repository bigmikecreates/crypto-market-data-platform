"""Azurite integration tests for the Azure Blob write/read path.

These tests require:
  1. adlfs installed:  pip install "cmpd[azure]"
  2. Azurite running:  docker run -p 10000:10000 mcr.microsoft.com/azure-storage/azurite

Set AZURE_STORAGE_CONNECTION_STRING to the Azurite connection string before running.
The default Azurite connection string is publicly known and contains no secrets.

Run selectively:
  pytest tests/integration/ -m azure_integration
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

# Skip the entire module when adlfs is not installed or Azurite isn't running.
adlfs = pytest.importorskip("adlfs", reason="adlfs not installed")

from crmd_platform.models.candle import Candle  # noqa: E402
from crmd_platform.models.funding_rate import FundingRate  # noqa: E402
from crmd_platform.query.duckdb_service import DuckDBQueryService  # noqa: E402
from crmd_platform.storage.parquet_writer import write_candles, write_funding_rates  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────────

# The Azurite devstoreaccount1 key is publicly documented — not a secret.
_AZURITE_DEFAULT = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
    "K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    "QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;"
    "TableEndpoint=http://127.0.0.1:10002/devstoreaccount1"
)

_CONN_STR = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", _AZURITE_DEFAULT)
_CONTAINER = "test-market-data"
_ACCOUNT = "devstoreaccount1"

pytestmark = pytest.mark.azure_integration


# ── Session-scoped fixtures ───────────────────────────────────────────────────


@pytest.fixture(scope="session")
def azure_fs():
    """adlfs filesystem pointed at Azurite, with test container pre-created."""
    from azure.storage.blob import BlobServiceClient

    svc = BlobServiceClient.from_connection_string(_CONN_STR)
    try:
        svc.create_container(_CONTAINER)
    except Exception:
        pass  # already exists from a previous run

    fs = adlfs.AzureBlobFileSystem(connection_string=_CONN_STR)
    # Quick connectivity check — skip the whole session if Azurite is unreachable.
    try:
        fs.ls(_ACCOUNT)
    except Exception as exc:
        pytest.skip(f"Azurite unreachable: {exc}")

    return fs


@pytest.fixture
def data_root(azure_fs):
    """A unique az:// URI per test so tests never share blobs."""
    prefix = uuid.uuid4().hex[:10]
    return f"az://{_CONTAINER}/{prefix}"


# ── Candle helpers ────────────────────────────────────────────────────────────


def _candle(
    ts: str,
    exchange: str = "kucoin",
    symbol: str = "BTC-USDT",
    tf: str = "1h",
    open_: str = "50000",
) -> Candle:
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=tf,
        timestamp=ts,
        open=open_,
        high="51000",
        low="49000",
        close="50500",
        volume="10",
        source="test",
    )


def _rate(
    ts: str, exchange: str = "bybit", symbol: str = "BTCUSDT", rate: str = "0.0001"
) -> FundingRate:
    return FundingRate(
        exchange=exchange,
        symbol=symbol,
        timestamp=ts,
        rate=rate,
        predicted_rate=rate,
        next_funding_time="2025-01-15T16:00:00",
        source="test",
    )


# ── Write / read round-trip ───────────────────────────────────────────────────


class TestCandleRoundTrip:
    def test_written_rows_are_queryable(self, data_root):
        candles = [
            _candle("2025-01-15T00:00:00"),
            _candle("2025-01-15T01:00:00"),
        ]
        write_candles(candles, base_path=data_root)

        svc = DuckDBQueryService()
        result = svc.get_candles(base_path=data_root, limit=10)
        assert len(result) == 2
        symbols = {c.symbol for c in result}
        assert symbols == {"BTC-USDT"}

    def test_multiple_partitions_all_returned(self, data_root):
        candles = [
            _candle("2025-01-14T23:00:00"),
            _candle("2025-01-15T00:00:00"),
        ]
        write_candles(candles, base_path=data_root)

        svc = DuckDBQueryService()
        result = svc.get_candles(base_path=data_root, limit=10)
        assert len(result) == 2

    def test_exchange_filter_works(self, data_root):
        candles = [
            _candle("2025-01-15T00:00:00", exchange="binance"),
            _candle("2025-01-15T01:00:00", exchange="kucoin"),
        ]
        write_candles(candles, base_path=data_root)

        svc = DuckDBQueryService()
        result = svc.get_candles(base_path=data_root, exchange="binance", limit=10)
        assert len(result) == 1
        assert result[0].exchange == "binance"


class TestFundingRateRoundTrip:
    def test_written_rows_are_queryable(self, data_root):
        rates = [_rate("2025-01-15T08:00:00"), _rate("2025-01-15T16:00:00")]
        write_funding_rates(rates, base_path=data_root)

        svc = DuckDBQueryService()
        result = svc.get_funding_rates(base_path=data_root, limit=10)
        assert len(result) == 2

    def test_list_datasets_shows_funding_rate(self, data_root):
        rates = [_rate("2025-01-15T08:00:00")]
        write_funding_rates(rates, base_path=data_root)

        svc = DuckDBQueryService()
        datasets = svc.list_datasets(base_path=data_root)
        assert "funding_rate" in datasets


# ── Idempotency ───────────────────────────────────────────────────────────────


class TestIdempotency:
    def test_refetch_does_not_duplicate_rows(self, data_root):
        candle = _candle("2025-01-15T00:00:00")
        write_candles([candle], base_path=data_root)
        write_candles([candle], base_path=data_root)  # exact same row

        svc = DuckDBQueryService()
        result = svc.get_candles(base_path=data_root, limit=10)
        assert len(result) == 1

    def test_corrected_value_replaces_stored_row(self, data_root):
        original = _candle("2025-01-15T00:00:00", open_="50000")
        write_candles([original], base_path=data_root)

        corrected = _candle("2025-01-15T00:00:00", open_="50100")
        write_candles([corrected], base_path=data_root)

        svc = DuckDBQueryService()
        result = svc.get_candles(base_path=data_root, limit=10)
        assert len(result) == 1
        assert result[0].open == "50100.0000000000"

    def test_new_rows_appended_without_touching_existing(self, data_root):
        write_candles([_candle("2025-01-15T00:00:00")], base_path=data_root)
        write_candles([_candle("2025-01-15T01:00:00")], base_path=data_root)

        svc = DuckDBQueryService()
        result = svc.get_candles(base_path=data_root, limit=10)
        assert len(result) == 2


# ── Concurrency: the key proof ────────────────────────────────────────────────


class TestConcurrentWrites:
    def test_concurrent_writes_same_partition_no_rows_lost(self, data_root):
        """Two workers writing different hours to the same daily partition must
        both survive. Without blob leases the last writer overwrites the first."""
        hours = [f"2025-01-15T{h:02d}:00:00" for h in range(8)]
        candles_per_worker = [
            [_candle(ts) for ts in hours[:4]],
            [_candle(ts) for ts in hours[4:]],
        ]

        def write_batch(batch):
            write_candles(batch, base_path=data_root)
            return len(batch)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write_batch, batch) for batch in candles_per_worker]
            counts = [f.result() for f in as_completed(futures)]

        assert sum(counts) == 8

        svc = DuckDBQueryService()
        result = svc.get_candles(base_path=data_root, limit=20)
        assert len(result) == 8, (
            f"Expected 8 rows (4 per worker), got {len(result)}. "
            "Rows lost to a write race — lease logic may be broken."
        )

    def test_concurrent_writes_different_partitions_no_interference(self, data_root):
        """Workers on distinct symbols never share a blob — no locking needed."""
        candles_a = [_candle("2025-01-15T00:00:00", symbol="BTC-USDT")]
        candles_b = [_candle("2025-01-15T00:00:00", symbol="ETH-USDT")]

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(write_candles, candles_a, data_root),
                pool.submit(write_candles, candles_b, data_root),
            ]
            for f in as_completed(futures):
                f.result()

        svc = DuckDBQueryService()
        result = svc.get_candles(base_path=data_root, limit=10)
        symbols = {c.symbol for c in result}
        assert symbols == {"BTC-USDT", "ETH-USDT"}

    def test_three_concurrent_workers_same_partition(self, data_root):
        """Stress the retry path with three simultaneous writers."""
        all_candles = [[_candle(f"2025-02-10T{h:02d}:00:00")] for h in range(9)]

        def write_one(batch):
            write_candles(batch, base_path=data_root)

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(write_one, batch) for batch in all_candles]
            for f in as_completed(futures):
                f.result()

        svc = DuckDBQueryService()
        result = svc.get_candles(base_path=data_root, limit=20)
        assert len(result) == 9


# ── Dataset discovery ─────────────────────────────────────────────────────────


class TestDatasetDiscovery:
    def test_list_datasets_finds_candles(self, data_root):
        write_candles([_candle("2025-01-15T00:00:00")], base_path=data_root)

        svc = DuckDBQueryService()
        datasets = svc.list_datasets(base_path=data_root)
        assert "candle" in datasets
        assert any("BTC-USDT" in k for k in datasets["candle"])

    def test_get_summary_returns_correct_counts(self, data_root):
        write_candles(
            [_candle("2025-01-15T00:00:00"), _candle("2025-01-15T01:00:00")],
            base_path=data_root,
        )

        svc = DuckDBQueryService()
        summary = svc.get_summary(base_path=data_root)
        assert len(summary) == 1
        assert summary[0]["rows"] == 2
        assert summary[0]["type"] == "candle"
