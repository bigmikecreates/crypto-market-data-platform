import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crmd_platform.benchmark.core import BenchmarkResult

_TRACKING_DIR = Path(
    os.environ.get(
        "CRMD_BENCHMARK_DIR",
        Path.home() / ".crmd" / "benchmarks",
    )
)
_RESULTS_FILE = _TRACKING_DIR / "results.jsonl"

_SEVERITY_THRESHOLDS = {
    "cpu_ms": {
        "fail": 0.10,
        "warn": 0.05,
    },
    "mem_mb": {
        "warn": 0.20,
    },
    "peak_mb": {
        "warn": 0.20,
    },
    "file_kb": {
        "fail": 0.50,
        "warn": 0.10,
    },
    "wall_ms": {
        "warn": 0.15,
    },
}


def _git_info() -> dict[str, str]:
    sha = ""
    ref = ""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        ).stdout.strip()
    except Exception:
        pass
    try:
        ref = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        ).stdout.strip()
    except Exception:
        pass
    return {"git_sha": sha, "git_ref": ref}


def _pipeline_stages(result: BenchmarkResult) -> list:
    return result.stages[: result.pipeline_end_index + 1]


def _build_summary(
    result: BenchmarkResult,
    ci_data: dict[str, tuple[float, float, float]] | None = None,
) -> dict[str, dict[str, float]]:
    pipe = _pipeline_stages(result)
    total_wall = sum(s.wall_ms for s in pipe)
    total_cpu = sum(s.cpu_ms for s in pipe)
    total_mem = sum(max(s.mem_delta_mb, 0) for s in pipe)
    peak = max((s.peak_mb for s in result.stages), default=0.0)
    file_kb = max(
        (s.file_kb for s in result.stages if s.file_kb is not None), default=0.0
    )
    g2 = sum(s.gc_g2 for s in pipe)
    cpu_wall = total_cpu / total_wall if total_wall > 0 else 0.0

    def _entry(
        metric: str,
        median: float,
        default_ci: tuple[float, float, float] | None = None,
    ) -> dict[str, float]:
        d: dict[str, float] = {"median": round(median, 2)}
        if ci_data and metric in ci_data:
            _, lo, hi = ci_data[metric]
            d["ci_lo"] = round(lo, 2)
            d["ci_hi"] = round(hi, 2)
        return d

    return {
        "wall_ms": _entry("wall_ms", total_wall),
        "cpu_ms": _entry("cpu_ms", total_cpu),
        "mem_mb": _entry("mem_mb", total_mem),
        "peak_mb": _entry("peak_mb", peak),
        "file_kb": _entry("file_kb", file_kb),
        "gc_g2": _entry("gc_g2", float(g2)),
        "cpu_wall_ratio": _entry("cpu_wall_ratio", cpu_wall),
    }


def _build_stages(result: BenchmarkResult) -> list[dict[str, Any]]:
    return [
        {
            "name": s.name,
            "wall_ms": s.wall_ms,
            "cpu_ms": s.cpu_ms,
            "mem_delta_mb": s.mem_delta_mb,
            "peak_mb": s.peak_mb,
            "gc_g0": s.gc_g0,
            "gc_g1": s.gc_g1,
            "gc_g2": s.gc_g2,
            "file_kb": s.file_kb,
        }
        for s in result.stages
    ]


def _build_rules(
    outcomes: list[tuple[str, str, str]],
) -> list[dict[str, str]]:
    return [{"name": n, "rating": r, "message": m} for n, r, m in outcomes]


def _pct_change(old: float, new: float) -> float | None:
    if old == 0:
        return None
    return (new - old) / abs(old)


def _classify_regression(
    metric: str,
    pct: float | None,
) -> tuple[str, str]:
    thresholds = _SEVERITY_THRESHOLDS.get(metric, {})
    fail = thresholds.get("fail")
    warn = thresholds.get("warn")

    if pct is not None and fail is not None and pct > fail:
        return "FAIL", f"regressed {pct:+.1%}"
    if pct is not None and warn is not None and pct > warn:
        return "WARN", f"regressed {pct:+.1%}"

    return "PASS", ""


def _classify_gc_regression(old_g2: int, new_g2: int) -> tuple[str, str]:
    if old_g2 == 0 and new_g2 > 0:
        return "WARN", f"GC gen-2 appeared: {old_g2} → {new_g2}"
    return "PASS", ""


class TrackingStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _RESULTS_FILE

    @property
    def path(self) -> Path:
        return self._path

    def save(
        self,
        result: BenchmarkResult,
        outcomes: list[tuple[str, str, str]],
        iterations: int = 1,
        ci_data: dict[str, tuple[float, float, float]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runner": result.runner_name,
            "count": result.count,
            "iterations": iterations,
            "ts_resolution": result.ts_resolution,
            "summary": _build_summary(result, ci_data),
            "stage_breakdown": _build_stages(result),
            "rules": _build_rules(outcomes),
            **_git_info(),
            **(extra or {}),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return entry

    def load_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with open(self._path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def load_last(self, n: int = 1) -> list[dict[str, Any]]:
        all_ = self.load_all()
        return all_[-n:] if all_ else []

    def compare(
        self,
        entry_a: dict[str, Any],
        entry_b: dict[str, Any],
    ) -> dict[str, Any]:
        sa, sb = entry_a["summary"], entry_b["summary"]
        metrics = ["cpu_ms", "wall_ms", "mem_mb", "peak_mb", "file_kb", "gc_g2"]

        summary: list[dict[str, Any]] = []
        final_verdict = "PASS"
        for m in metrics:
            va = sa.get(m, {}).get("median", 0)
            vb = sb.get(m, {}).get("median", 0)
            pct = _pct_change(va, vb)

            verdict, reason = _classify_regression(m, pct)
            if m == "gc_g2" and verdict == "PASS":
                v, r = _classify_gc_regression(int(va), int(vb))
                verdict, reason = v, r

            if verdict == "FAIL":
                final_verdict = "FAIL"
            elif verdict == "WARN" and final_verdict != "FAIL":
                final_verdict = "WARN"

            summary.append(
                {
                    "metric": m,
                    "label": _metric_label(m),
                    "old": va,
                    "new": vb,
                    "pct": pct,
                    "verdict": verdict,
                    "reason": reason,
                }
            )

        rules_a = {r["name"]: r["rating"] for r in entry_a.get("rules", [])}
        rules_b = {r["name"]: r["rating"] for r in entry_b.get("rules", [])}
        rule_changes: list[dict[str, str]] = []
        for name in rules_a | rules_b:
            old_r = rules_a.get(name, "PASS")
            new_r = rules_b.get(name, "PASS")
            if old_r != new_r:
                severity_order = {"PASS": 0, "WARN": 1, "FAIL": 2}
                old_sev = severity_order.get(old_r, 0)
                new_sev = severity_order.get(new_r, 0)
                if new_sev > old_sev:
                    rv = "FAIL" if new_r == "FAIL" else "WARN"
                else:
                    rv = "PASS"
                if rv == "FAIL":
                    final_verdict = "FAIL"
                elif rv == "WARN" and final_verdict != "FAIL":
                    final_verdict = "WARN"
                rule_changes.append(
                    {
                        "name": name,
                        "old_rating": old_r,
                        "new_rating": new_r,
                        "verdict": rv,
                    }
                )

        stage_deltas: list[dict[str, Any]] = []
        stages_a = {s["name"]: s for s in entry_a.get("stage_breakdown", [])}
        stages_b = {s["name"]: s for s in entry_b.get("stage_breakdown", [])}
        all_names = set(stages_a) | set(stages_b)
        for name in sorted(all_names):
            va = stages_a.get(name, {}).get("wall_ms", 0)
            vb = stages_b.get(name, {}).get("wall_ms", 0)
            delta = vb - va
            if abs(delta) < 0.1:
                continue
            pct = _pct_change(va, vb)
            pct_str = f"{pct:+.1%}" if pct is not None else "new"
            stage_deltas.append(
                {
                    "name": name,
                    "old_wall": va,
                    "new_wall": vb,
                    "delta": round(delta, 2),
                    "pct_str": pct_str,
                }
            )
        stage_deltas.sort(key=lambda x: abs(x["delta"]), reverse=True)

        return {
            "entry_a": entry_a,
            "entry_b": entry_b,
            "summary": summary,
            "rule_changes": rule_changes,
            "stage_deltas": stage_deltas[:5],
            "final_verdict": final_verdict,
        }

    def trends(
        self,
        entries: list[dict[str, Any]],
        metric: str,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        prev: float | None = None
        for i, e in enumerate(entries):
            val = e.get("summary", {}).get(metric, {}).get("median", 0)
            pct = _pct_change(prev, val) if prev is not None else None
            result.append(
                {
                    "index": i,
                    "timestamp": e.get("timestamp", ""),
                    "git_sha": e.get("git_sha", ""),
                    "runner": e.get("runner", ""),
                    "value": val,
                    "pct": pct,
                }
            )
            prev = val
        return result


def _metric_label(m: str) -> str:
    labels = {
        "cpu_ms": "CPU time (ms)",
        "wall_ms": "Wall-clock (ms)",
        "mem_mb": "Memory delta (MB)",
        "peak_mb": "Peak memory (MB)",
        "file_kb": "File size (KB)",
        "gc_g2": "GC gen-2",
    }
    return labels.get(m, m)
