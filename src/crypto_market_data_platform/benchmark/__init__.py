from crypto_market_data_platform.benchmark.core import (
    BenchmarkContext,
    BenchmarkResult,
    PipelineRunner,
    StageMetrics,
)
from crypto_market_data_platform.benchmark.rules import CrossValidationRule, evaluate_rules
from crypto_market_data_platform.benchmark.runners import CandlePipelineRunner

RUNNERS: dict[str, type[PipelineRunner]] = {
    "candle": CandlePipelineRunner,
}

__all__ = [
    "BenchmarkContext",
    "BenchmarkResult",
    "CandlePipelineRunner",
    "CrossValidationRule",
    "PipelineRunner",
    "RUNNERS",
    "StageMetrics",
    "evaluate_rules",
]
