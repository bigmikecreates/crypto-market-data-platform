from crmd_platform.benchmark.core import (
    BenchmarkContext,
    BenchmarkResult,
    PipelineRunner,
    StageMetrics,
)
from crmd_platform.benchmark.rules import (
    CrossValidationRule,
    evaluate_rules,
)
from crmd_platform.benchmark.runners import (
    CandlePipelineRunner,
    ProviderCandlePipelineRunner,
)

RUNNERS: dict[str, type[PipelineRunner]] = {
    "candle": CandlePipelineRunner,
    "provider": ProviderCandlePipelineRunner,
}

__all__ = [
    "BenchmarkContext",
    "BenchmarkResult",
    "CandlePipelineRunner",
    "CrossValidationRule",
    "PipelineRunner",
    "ProviderCandlePipelineRunner",
    "RUNNERS",
    "StageMetrics",
    "evaluate_rules",
]
