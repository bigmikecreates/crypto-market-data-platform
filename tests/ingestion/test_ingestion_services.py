import pytest
import pyarrow.parquet as pq

from datetime import datetime, timezone

from crmd_platform.ingestion import OHLCVService, FundingRateService
from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.providers.fake import FakeProvider
from crmd_platform.storage import create_backend


_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
_END = datetime(2026, 1, 2, tzinfo=timezone.utc)


class TestOhlcvService:
    def test_ingest_writes_candles(self, tmp_path):
        svc = OHLCVService(provider=FakeProvider())
        count = svc.ingest(
            symbol="BTC/USDT",
            timeframe="1h",
            start=_START,
            end=_END,
            base_path=str(tmp_path),
            backend=create_backend(str(tmp_path)),
        )
        assert count == 1
        files = list(tmp_path.rglob("*.parquet"))
        assert len(files) == 1
        table = pq.read_table(str(files[0]))
        assert table.num_rows == 1

    def test_ingest_blocks_on_validation_failure(self, tmp_path):
        class BadProvider(FakeProvider):
            def fetch_ohlcv(self, symbol, timeframe, start, end):
                return [
                    Candle(
                        exchange="fake",
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp="2026-01-01T00:00:00",
                        open="",
                        high="110",
                        low="90",
                        close="105",
                        volume="10",
                        source="fake",
                    )
                ]

        svc = OHLCVService(provider=BadProvider())
        with pytest.raises(ValueError, match="Validation failed"):
            svc.ingest(
                symbol="BTC/USDT",
                timeframe="1h",
                start=_START,
                end=_END,
                base_path=str(tmp_path),
                backend=create_backend(str(tmp_path)),
            )
        assert list(tmp_path.rglob("*.parquet")) == []


class TestFundingRateService:
    def test_ingest_writes_rates(self, tmp_path):
        svc = FundingRateService(provider=FakeProvider())
        count = svc.ingest(
            symbol="BTC/USDT",
            start=_START,
            end=_END,
            base_path=str(tmp_path),
            backend=create_backend(str(tmp_path)),
        )
        assert count == 1
        files = list(tmp_path.rglob("*.parquet"))
        assert len(files) == 1

    def test_ingest_blocks_on_validation_failure(self, tmp_path):
        class BadFundingProvider(FakeProvider):
            def fetch_funding_rates(self, symbol, start, end):
                return [
                    FundingRate(
                        exchange="fake",
                        symbol=symbol,
                        timestamp="2026-01-01T00:00:00",
                        rate="",
                        predicted_rate="0.0002",
                        next_funding_time="2026-01-01T08:00:00",
                        source="fake",
                    )
                ]

        svc = FundingRateService(provider=BadFundingProvider())
        with pytest.raises(ValueError, match="Validation failed"):
            svc.ingest(
                symbol="BTC/USDT",
                start=_START,
                end=_END,
                base_path=str(tmp_path),
                backend=create_backend(str(tmp_path)),
            )
        assert list(tmp_path.rglob("*.parquet")) == []
