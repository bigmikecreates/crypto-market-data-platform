from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import gc
import time
import tracemalloc

from crypto_market_data_platform.config import TimestampConfig


@dataclass
class StageMetrics:
    name: str
    wall_ms: float
    cpu_ms: float
    mem_delta_mb: float
    peak_mb: float
    gc_g0: int
    gc_g1: int
    gc_g2: int
    file_kb: float | None = None


@dataclass
class BenchmarkResult:
    count: int
    ts_resolution: str
    runner_name: str
    stages: list[StageMetrics] = field(default_factory=list)
    schema: dict[str, str] = field(default_factory=dict)
    pipeline_end_index: int = 0
    validation_issues: int = 0


class BenchmarkContext:
    def __init__(self) -> None:
        self.stages: list[StageMetrics] = []
        self._last_wall = time.perf_counter()
        self._last_cpu = time.process_time()
        self._last_gc = gc.get_stats()

    def checkpoint(
        self,
        name: str,
        file_kb: float | None = None,
    ) -> None:
        now_wall = time.perf_counter()
        now_cpu = time.process_time()
        now_mem = tracemalloc.get_traced_memory()
        now_gc = gc.get_stats()

        wall_delta = (now_wall - self._last_wall) * 1000.0
        cpu_delta = (now_cpu - self._last_cpu) * 1000.0
        mem_current = now_mem[0]
        mem_peak = now_mem[1]

        g0 = now_gc[0]["collections"] - self._last_gc[0]["collections"]
        g1 = now_gc[1]["collections"] - self._last_gc[1]["collections"]
        g2 = now_gc[2]["collections"] - self._last_gc[2]["collections"]

        self.stages.append(
            StageMetrics(
                name=name,
                wall_ms=round(max(wall_delta, 0), 2),
                cpu_ms=round(max(cpu_delta, 0), 2),
                mem_delta_mb=round(mem_current / (1024 * 1024), 2),
                peak_mb=round(mem_peak / (1024 * 1024), 2),
                gc_g0=g0,
                gc_g1=g1,
                gc_g2=g2,
                file_kb=file_kb,
            )
        )

        self._last_wall = now_wall
        self._last_cpu = now_cpu
        self._last_gc = now_gc
        tracemalloc.clear_traces()

    @property
    def total_mem_delta_mb(self) -> float:
        return sum(max(s.mem_delta_mb, 0) for s in self.stages)


class PipelineRunner(ABC):
    @abstractmethod
    def run_coarse(
        self,
        count: int,
        ts_config: TimestampConfig,
        base_path: str,
    ) -> BenchmarkResult: ...

    def run_verbose(
        self,
        count: int,
        ts_config: TimestampConfig,
        base_path: str,
    ) -> BenchmarkResult:
        return self.run_coarse(count, ts_config, base_path)
