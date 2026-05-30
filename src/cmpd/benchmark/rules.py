from collections.abc import Callable
from dataclasses import dataclass

from cmpd.benchmark.core import BenchmarkResult


@dataclass
class CrossValidationRule:
    name: str
    evaluate: Callable[[BenchmarkResult], tuple[str, str]]
    recommendation: str | None = None


def _pipeline_stages(result: BenchmarkResult) -> list:
    return result.stages[: result.pipeline_end_index + 1]


def _total_wall(result: BenchmarkResult) -> float:
    return sum(s.wall_ms for s in _pipeline_stages(result))


def _total_cpu(result: BenchmarkResult) -> float:
    return sum(s.cpu_ms for s in _pipeline_stages(result))


def _total_mem(result: BenchmarkResult) -> float:
    return sum(max(s.mem_delta_mb, 0) for s in _pipeline_stages(result))


def _peak_mem(result: BenchmarkResult) -> float:
    return max((s.peak_mb for s in result.stages), default=0.0)


def _write_stage_wall(result: BenchmarkResult) -> float:
    for s in reversed(_pipeline_stages(result)):
        if s.name == "Parquet write":
            return s.wall_ms
    return 0.0


def _file_size_mb(result: BenchmarkResult) -> float:
    for s in reversed(result.stages):
        if s.file_kb is not None:
            return s.file_kb / 1024
    return 0.0


def _total_gc_gen2(result: BenchmarkResult) -> int:
    return sum(s.gc_g2 for s in _pipeline_stages(result))


def _total_gc_any(result: BenchmarkResult) -> int:
    return sum(s.gc_g0 + s.gc_g1 + s.gc_g2 for s in _pipeline_stages(result))


# ── Rule: Compression ratio ─────────────────────────────────────
def _eval_compression(result: BenchmarkResult) -> tuple[str, str]:
    mem_mb = _total_mem(result)
    file_mb = _file_size_mb(result)
    if mem_mb <= 0 or file_mb <= 0:
        return "PASS", "No file written — nothing to compare."
    ratio = mem_mb / file_mb
    if ratio < 5:
        return "PASS", f"{ratio:.1f}× — in-memory representation is already tight."
    elif ratio < 15:
        return "PASS", f"{ratio:.1f}× — typical for decimal128 + dict encoding."
    elif ratio < 30:
        return (
            "WARN",
            f"{ratio:.1f}× — in-memory far exceeds disk. Check for buffer bloat.",
        )
    else:
        return "FAIL", f"{ratio:.1f}× — massive gap. Investigate allocation pattern."


# ── Rule: CPU/Wall ratio ─────────────────────────────────────────
def _eval_cpu_wall(result: BenchmarkResult) -> tuple[str, str]:
    total_w = _total_wall(result)
    total_c = _total_cpu(result)
    if total_w <= 0:
        return "PASS", "No measurable wall time."
    ratio = total_c / total_w
    if ratio >= 0.8:
        return "PASS", f"{ratio:.2f} — near 1.0, no I/O or lock contention."
    elif ratio >= 0.5:
        return (
            "WARN",
            f"{ratio:.2f} — moderate non-CPU overhead (allocation, page faults).",
        )
    else:
        return "FAIL", f"{ratio:.2f} — high I/O or lock contention. Investigate."


# ── Rule: GC gen-2 count ─────────────────────────────────────────
def _eval_gc_gen2(result: BenchmarkResult) -> tuple[str, str]:
    g2 = _total_gc_gen2(result)
    n = result.count
    if n <= 0:
        return "PASS", "No candles measured."
    if g2 == 0:
        return "PASS", "Zero gen-2 collections — no long-lived garbage."
    elif g2 <= max(5, n // 5000):
        return "PASS", f"{g2} gen-2 collection(s) — within acceptable range."
    elif g2 <= max(20, n // 1000):
        return (
            "WARN",
            f"{g2} gen-2 collection(s) — moderate. Review temporary object lifetimes.",
        )
    else:
        return (
            "FAIL",
            f"{g2} gen-2 collection(s) — excessive. Investigate allocation churn.",
        )


# ── Rule: Parquet write dominance ────────────────────────────────
def _eval_write_dominance(result: BenchmarkResult) -> tuple[str, str]:
    total = _total_wall(result)
    write = _write_stage_wall(result)
    if total <= 0:
        return "PASS", "No measurable wall time."
    pct = (write / total) * 100
    if pct < 40:
        return "PASS", f"{pct:.0f}% — write is not the bottleneck."
    elif pct < 60:
        return "PASS", f"{pct:.0f}% — I/O is dominant but within expected range."
    elif pct < 80:
        return (
            "WARN",
            f"{pct:.0f}% — I/O strongly dominates. Disk speed may be the constraint.",
        )
    else:
        return (
            "FAIL",
            f"{pct:.0f}% — nearly all time is I/O. Upgrade disk or reduce write count.",
        )


# ── Rule: Peak vs total allocated memory ─────────────────────────
def _eval_peak_vs_allocated(result: BenchmarkResult) -> tuple[str, str]:
    peak = _peak_mem(result)
    total_mem = _total_mem(result)
    if total_mem <= 0:
        return "PASS", "No measurable allocation."
    ratio = peak / total_mem
    if ratio < 1.5:
        return "PASS", f"{ratio:.1f}× — PyArrow buffer pre-allocation is efficient."
    elif ratio < 2.5:
        return (
            "PASS",
            f"{ratio:.1f}× — moderate buffer overhead, expected for columnar data.",
        )
    elif ratio < 4:
        return "WARN", f"{ratio:.1f}× — peak far exceeds total. Consider chunking."
    else:
        return "FAIL", f"{ratio:.1f}× — extreme buffer bloat. Restructure batch writes."


# ── Verbose-only: Validation overhead ────────────────────────────
def _eval_validation_overhead(result: BenchmarkResult) -> tuple[str, str]:
    total = _total_wall(result)
    validate_ms = 0.0
    for s in result.stages:
        if "cast" in s.name.lower() or "valid" in s.name.lower():
            validate_ms += s.wall_ms
    if total <= 0 or validate_ms <= 0:
        return "PASS", "No validation stage measured."
    pct = (validate_ms / total) * 100
    if pct < 2:
        return "PASS", f"{pct:.1f}% — validation overhead is negligible."
    elif pct < 5:
        return "PASS", f"{pct:.1f}% — validation cost is acceptable."
    elif pct < 10:
        return (
            "WARN",
            f"{pct:.1f}% — validation is noticeable. Consider simplifying regex.",
        )
    else:
        return (
            "FAIL",
            f"{pct:.1f}% — validation dominates. Move to bulk C++ validation.",
        )


# ── Verbose-only: Column conversion cost ─────────────────────────
def _eval_conversion_cost(result: BenchmarkResult) -> tuple[str, str]:
    total = _total_wall(result)
    convert_ms = 0.0
    for s in result.stages:
        if "cast" in s.name.lower() or "conversion" in s.name.lower():
            convert_ms += s.wall_ms
    if total <= 0 or convert_ms <= 0:
        return "PASS", "No conversion stage measured."
    pct = (convert_ms / total) * 100
    if pct < 10:
        return "PASS", f"{pct:.1f}% — C++ .cast() is efficient."
    elif pct < 20:
        return "PASS", f"{pct:.1f}% — conversion cost is within expected range."
    elif pct < 35:
        return (
            "WARN",
            f"{pct:.1f}% — conversion is a significant cost. Consider batch tuning.",
        )
    else:
        return (
            "FAIL",
            f"{pct:.1f}% — conversion dominates. Investigate per-column type casting.",
        )


# ── Default rules ────────────────────────────────────────────────
DEFAULT_RULES: list[CrossValidationRule] = [
    CrossValidationRule(
        "MemΔ vs file size",
        _eval_compression,
        "If failing, review Arrow buffer allocation or Parquet row-group size.",
    ),
    CrossValidationRule(
        "CPU/Wall ratio",
        _eval_cpu_wall,
        "If failing, profile for I/O bottlenecks or lock contention.",
    ),
    CrossValidationRule(
        "GC gen-2 count",
        _eval_gc_gen2,
        "If failing, check for long-lived temporary structures in the hot path.",
    ),
    CrossValidationRule(
        "Parquet write dominance",
        _eval_write_dominance,
        "If failing, consider faster storage or asynchronous write.",
    ),
    CrossValidationRule(
        "Peak vs total allocated",
        _eval_peak_vs_allocated,
        "If failing, set pa.Table.from_pydict chunk_size to limit pre-allocation.",
    ),
]

VERBOSE_RULES: list[CrossValidationRule] = DEFAULT_RULES + [
    CrossValidationRule(
        "Validation overhead",
        _eval_validation_overhead,
        "If failing, move validation to C++ level or reduce regex complexity.",
    ),
    CrossValidationRule(
        "Column conversion cost",
        _eval_conversion_cost,
        "If failing, review type casting strategy or batch size.",
    ),
]


def evaluate_rules(
    rules: list[CrossValidationRule],
    result: BenchmarkResult,
) -> list[tuple[str, str, str]]:
    outcomes: list[tuple[str, str, str]] = []
    for rule in rules:
        rating, message = rule.evaluate(result)
        outcomes.append((rule.name, rating, message))
    return outcomes
