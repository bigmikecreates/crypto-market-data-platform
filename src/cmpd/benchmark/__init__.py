from cmpd.benchmark.core import (
    BenchmarkContext,
    BenchmarkResult,
    PipelineRunner,
    StageMetrics,
)
from cmpd.benchmark.rules import (
    CrossValidationRule,
    evaluate_rules,
)
from cmpd.benchmark.runners import (
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
