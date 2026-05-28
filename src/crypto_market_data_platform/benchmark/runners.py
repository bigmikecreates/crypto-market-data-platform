from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from crypto_market_data_platform.benchmark.core import (
    BenchmarkContext,
    BenchmarkResult,
    PipelineRunner,
)
from crypto_market_data_platform.config import TimestampConfig
from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.base import OHLCVProvider
from crypto_market_data_platform.storage.parquet_writer import (
    _to_decimal128,
    _to_timestamp,
    candle_to_table,
)
from crypto_market_data_platform.validation.candles import validate_candle_batch


def _make_candles(count: int) -> list[Candle]:
    return [
        Candle(
            exchange="fake",
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=f"2026-05-27T{(i // 60) % 24:02d}:{i % 60:02d}:00",
            open=str(100 + i % 50),
            high=str(110 + i % 50),
            low=str(90 + i % 30),
            close=str(105 + i % 40),
            volume=str(10 + (i * 7) % 100),
            source="benchmark",
        )
        for i in range(count)
    ]


def _stat_kb(path: Path) -> float:
    return round(path.stat().st_size / 1024, 2)


def _file_size(stages: list[Any]) -> float:
    for s in reversed(stages):
        if s.file_kb is not None:
            return s.file_kb
    return 0.0


class CandlePipelineRunner(PipelineRunner):
    def run_coarse(
        self,
        count: int,
        ts_config: TimestampConfig,
        base_path: str,
    ) -> BenchmarkResult:
        ctx = BenchmarkContext()
        result = BenchmarkResult(
            count=count,
            ts_resolution=ts_config.resolution,
            runner_name="candle",
        )

        ctx.checkpoint("Baseline")

        candles = _make_candles(count)
        if count == 0:
            result.stages = ctx.stages
            return result

        ctx.checkpoint("Candle creation")

        table = candle_to_table(candles, ts_config)
        ctx.checkpoint("Table assembly")

        write_dir = Path(base_path) / "bench"
        write_dir.mkdir(parents=True, exist_ok=True)
        path = write_dir / "out.parquet"
        pq.write_table(table, str(path))
        fsize = _stat_kb(path)
        ctx.checkpoint("Parquet write", file_kb=fsize)

        result.pipeline_end_index = len(ctx.stages) - 1

        schema = pq.read_schema(str(path))
        result.schema = {f.name: str(f.type) for f in schema}
        ctx.checkpoint("Read schema")

        pq.read_table(str(path))
        ctx.checkpoint("Read + verify", file_kb=fsize)

        result.stages = ctx.stages
        return result

    def run_verbose(
        self,
        count: int,
        ts_config: TimestampConfig,
        base_path: str,
    ) -> BenchmarkResult:
        ctx = BenchmarkContext()
        result = BenchmarkResult(
            count=count,
            ts_resolution=ts_config.resolution,
            runner_name="candle",
        )

        ctx.checkpoint("Baseline")

        candles = _make_candles(count)
        if count == 0:
            result.stages = ctx.stages
            return result

        ctx.checkpoint("Candle creation")

        key = "bench/BTC/USDT/1h"
        open_vals = [c.open for c in candles]
        high_vals = [c.high for c in candles]
        low_vals = [c.low for c in candles]
        close_vals = [c.close for c in candles]
        volume_vals = [c.volume for c in candles]
        ts_vals = [c.timestamp for c in candles]
        exchange_vals = [c.exchange for c in candles]
        symbol_vals = [c.symbol for c in candles]
        tf_vals = [c.timeframe for c in candles]
        source_vals = [c.source for c in candles]
        ctx.checkpoint("Column extract")

        open_arr = _to_decimal128(open_vals, "open", key)
        high_arr = _to_decimal128(high_vals, "high", key)
        low_arr = _to_decimal128(low_vals, "low", key)
        close_arr = _to_decimal128(close_vals, "close", key)
        volume_arr = _to_decimal128(volume_vals, "volume", key)
        ctx.checkpoint("decimal128 cast")

        ts_arr = _to_timestamp(ts_vals, ts_config)
        ctx.checkpoint("timestamp cast")

        table = pa.table(
            {
                "exchange": pa.array(exchange_vals, type=pa.string()),
                "symbol": pa.array(symbol_vals, type=pa.string()),
                "timeframe": pa.array(tf_vals, type=pa.string()),
                "timestamp": ts_arr,
                "open": open_arr,
                "high": high_arr,
                "low": low_arr,
                "close": close_arr,
                "volume": volume_arr,
                "source": pa.array(source_vals, type=pa.string()),
            }
        )
        ctx.checkpoint("Table assembly")

        write_dir = Path(base_path) / "bench"
        write_dir.mkdir(parents=True, exist_ok=True)
        path = write_dir / "out.parquet"
        pq.write_table(table, str(path))
        fsize = _stat_kb(path)
        ctx.checkpoint("Parquet write", file_kb=fsize)

        result.pipeline_end_index = len(ctx.stages) - 1

        schema = pq.read_schema(str(path))
        result.schema = {f.name: str(f.type) for f in schema}
        ctx.checkpoint("Read schema")

        pq.read_table(str(path))
        ctx.checkpoint("Read + verify", file_kb=fsize)

        result.stages = ctx.stages
        return result


class ProviderCandlePipelineRunner(PipelineRunner):
    def __init__(
        self,
        provider: OHLCVProvider,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> None:
        self._provider = provider
        self._symbol = symbol
        self._timeframe = timeframe
        self._start = start
        self._end = end

    def run_coarse(
        self,
        count: int,
        ts_config: TimestampConfig,
        base_path: str,
    ) -> BenchmarkResult:
        ctx = BenchmarkContext()
        candles: list[Candle] = []

        ctx.checkpoint("Baseline")

        if self._start and self._end:
            candles = self._provider.fetch_ohlcv(
                symbol=self._symbol,
                timeframe=self._timeframe,
                start=self._start,
                end=self._end,
            )
        ctx.checkpoint("Provider fetch")

        actual_count = len(candles)
        result = BenchmarkResult(
            count=actual_count,
            ts_resolution=ts_config.resolution,
            runner_name=self._provider.__class__.__name__.replace(
                "Provider", ""
            ).lower(),
        )

        if actual_count == 0:
            result.stages = ctx.stages
            return result

        issues = validate_candle_batch(candles)
        ctx.checkpoint("Validation")

        table = candle_to_table(candles, ts_config)
        ctx.checkpoint("Table assembly")

        write_dir = Path(base_path) / "bench"
        write_dir.mkdir(parents=True, exist_ok=True)
        path = write_dir / "out.parquet"
        pq.write_table(table, str(path))
        fsize = _stat_kb(path)
        ctx.checkpoint("Parquet write", file_kb=fsize)

        result.pipeline_end_index = len(ctx.stages) - 1
        result.validation_issues = len(issues.issues)

        schema = pq.read_schema(str(path))
        result.schema = {f.name: str(f.type) for f in schema}
        ctx.checkpoint("Read schema")

        pq.read_table(str(path))
        ctx.checkpoint("Read + verify", file_kb=fsize)

        result.stages = ctx.stages
        return result

    def run_verbose(
        self,
        count: int,
        ts_config: TimestampConfig,
        base_path: str,
    ) -> BenchmarkResult:
        ctx = BenchmarkContext()
        candles: list[Candle] = []

        ctx.checkpoint("Baseline")

        if self._start and self._end:
            candles = self._provider.fetch_ohlcv(
                symbol=self._symbol,
                timeframe=self._timeframe,
                start=self._start,
                end=self._end,
            )
        ctx.checkpoint("Provider fetch")

        actual_count = len(candles)
        result = BenchmarkResult(
            count=actual_count,
            ts_resolution=ts_config.resolution,
            runner_name=self._provider.__class__.__name__.replace(
                "Provider", ""
            ).lower(),
        )

        if actual_count == 0:
            result.stages = ctx.stages
            return result

        issues = validate_candle_batch(candles)
        ctx.checkpoint("Validation")

        open_vals = [c.open for c in candles]
        high_vals = [c.high for c in candles]
        low_vals = [c.low for c in candles]
        close_vals = [c.close for c in candles]
        volume_vals = [c.volume for c in candles]
        ts_vals = [c.timestamp for c in candles]
        exchange_vals = [c.exchange for c in candles]
        symbol_vals = [c.symbol for c in candles]
        tf_vals = [c.timeframe for c in candles]
        source_vals = [c.source for c in candles]
        ctx.checkpoint("Column extract")

        key = f"bench/{self._symbol}/{self._timeframe}"
        open_arr = _to_decimal128(open_vals, "open", key)
        high_arr = _to_decimal128(high_vals, "high", key)
        low_arr = _to_decimal128(low_vals, "low", key)
        close_arr = _to_decimal128(close_vals, "close", key)
        volume_arr = _to_decimal128(volume_vals, "volume", key)
        ctx.checkpoint("decimal128 cast")

        ts_arr = _to_timestamp(ts_vals, ts_config)
        ctx.checkpoint("timestamp cast")

        table = pa.table(
            {
                "exchange": pa.array(exchange_vals, type=pa.string()),
                "symbol": pa.array(symbol_vals, type=pa.string()),
                "timeframe": pa.array(tf_vals, type=pa.string()),
                "timestamp": ts_arr,
                "open": open_arr,
                "high": high_arr,
                "low": low_arr,
                "close": close_arr,
                "volume": volume_arr,
                "source": pa.array(source_vals, type=pa.string()),
            }
        )
        ctx.checkpoint("Table assembly")

        write_dir = Path(base_path) / "bench"
        write_dir.mkdir(parents=True, exist_ok=True)
        path = write_dir / "out.parquet"
        pq.write_table(table, str(path))
        fsize = _stat_kb(path)
        ctx.checkpoint("Parquet write", file_kb=fsize)

        result.pipeline_end_index = len(ctx.stages) - 1
        result.validation_issues = len(issues.issues)

        schema = pq.read_schema(str(path))
        result.schema = {f.name: str(f.type) for f in schema}
        ctx.checkpoint("Read schema")

        pq.read_table(str(path))
        ctx.checkpoint("Read + verify", file_kb=fsize)

        result.stages = ctx.stages
        return result
