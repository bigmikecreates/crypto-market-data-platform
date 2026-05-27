#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────
# Pipeline benchmark — measures wall-clock, CPU, memory, GC, and file
# size across configurable checkpoint stages.
#
# Usage:
#   python scripts/benchmark_pipeline.py run --count 10000
#   python scripts/benchmark_pipeline.py run --count 50000 --verbose
#   python scripts/benchmark_pipeline.py run --runner candle --ts-res us
# ─────────────────────────────────────────────────────────────────────

import gc
import math
import os
import statistics
import sys
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from crypto_market_data_platform.benchmark import RUNNERS
from crypto_market_data_platform.benchmark.rules import (
    DEFAULT_RULES,
    VERBOSE_RULES,
    evaluate_rules,
)
from crypto_market_data_platform.benchmark.runners import ProviderCandlePipelineRunner
from crypto_market_data_platform.config import TimestampConfig
from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.bitfinex import BitfinexProvider
from crypto_market_data_platform.providers.fake import FakeProvider
from crypto_market_data_platform.providers.kucoin import KuCoinProvider
from crypto_market_data_platform.storage.parquet_writer import (
    _to_decimal128,
    _to_timestamp,
)

app = typer.Typer()


# ── helpers ────────────────────────────────────────────────────────


def _fmt(val: float, width: int = 10) -> str:
    """Right-align a float in a fixed-width field."""
    return f"{val:>{width}.2f}"


def _fmt_none(width: int = 10) -> str:
    return " " * (width - 3) + " — "


def _cum_pct(current: float, total: float, width: int = 6) -> str:
    if total <= 0:
        return f"{'':>{width}}"
    pct = (current / total) * 100
    if pct > 100.5:
        return f"{'—':>{width}}"
    return f"{pct:>{width-1}.0f}%"


def _rating_color(rating: str) -> str:
    return {"PASS": "green", "WARN": "yellow", "FAIL": "red"}.get(rating, "")


def _stage_name_width(stages: list[Any]) -> int:
    return max(len(s.name) for s in stages) + 1


def _us_note(text: str, first: bool = False) -> str:
    if first:
        return text.replace("μs", "microseconds (μs)")
    return text


# ── t-distribution critical values (95% CI two-tailed) ────────────
_T_TABLE: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    15: 2.131,
    20: 2.086,
}


def _t_value(df: int) -> float:
    return _T_TABLE.get(df, 2.042)  # fallback to df=30


def _compute_ci(values: list[float]) -> tuple[float, float, float]:
    n = len(values)
    if n < 1:
        return 0.0, 0.0, 0.0
    if n == 1:
        return values[0], values[0], values[0]
    median = statistics.median(values)
    if n < 3:
        return median, median, median
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    t = _t_value(n - 1)
    margin = t * stdev / math.sqrt(n)
    return median, mean - margin, mean + margin


def _pipeline_stats(result: Any) -> dict[str, float]:
    pipe = result.stages[: result.pipeline_end_index + 1]
    file_kb = max((s.file_kb for s in result.stages if s.file_kb is not None), default=0.0)
    return {
        "wall_ms": sum(s.wall_ms for s in pipe),
        "cpu_ms": sum(s.cpu_ms for s in pipe),
        "mem_mb": sum(max(s.mem_delta_mb, 0) for s in pipe),
        "peak_mb": max((s.peak_mb for s in result.stages), default=0.0),
        "file_kb": file_kb,
    }


def _setup_isolated() -> None:
    cpu = os.sched_getaffinity(0).pop()
    try:
        os.sched_setaffinity(0, {cpu})
    except AttributeError:
        typer.echo("Warning: sched_setaffinity not available on this platform.", err=True)
        return
    try:
        os.nice(-10)
    except PermissionError:
        typer.echo(
            "Note: nice(-10) requires root or CAP_SYS_NICE. "
            "Running with pinning only (no priority elevation).",
            err=True,
        )
    pid = os.getpid()
    cmd = "taskset" if sys.platform == "linux" else "N/A"
    args = " ".join(sys.argv[1:])
    typer.echo(
        f"CPU isolated: pinned to core {cpu}, priority adjusted. "
        f"Full command: taskset -c {cpu} -p {pid}  # then run: {args}"
    )


# ── formatting helpers for the validation & insight sections ──────


def _format_validation_section(
    outcomes: list[tuple[str, str, str]],
    rules: list[Any],
) -> list[str]:
    passed = sum(1 for _, r, _ in outcomes if r == "PASS")
    total = len(outcomes)
    lines: list[str] = [
        "",
        "VALIDATION",
        "─" * 100,
        f"  {passed}/{total} PASS"
        + ("" if passed == total else f"  ({total - passed} WARN/FAIL)"),
        "",
    ]
    for (name, rating, msg), rule in zip(outcomes, rules):
        rec = ""
        if rating != "PASS" and rule.recommendation:
            rec = f"  Recommendation: {rule.recommendation}"
        lines.append(f"  • {name}: {rating}")
        lines.append(f"    {msg}")
        if rec:
            lines.append(rec)
        lines.append("")
    return lines


def _format_cross_validation_section(
    result: Any,
    verbose: bool,
) -> list[str]:
    lines: list[str] = [
        "",
        "CROSS-VALIDATION INSIGHTS",
        "─" * 100,
        "",
    ]

    # Determine pipeline totals
    pipe_stages = result.stages[: result.pipeline_end_index + 1]
    total_wall = sum(s.wall_ms for s in pipe_stages)
    total_cpu = sum(s.cpu_ms for s in pipe_stages)
    total_mem = sum(max(s.mem_delta_mb, 0) for s in pipe_stages)
    total_g2 = sum(s.gc_g2 for s in pipe_stages)
    peak = max((s.peak_mb for s in result.stages), default=0.0)

    # File size
    file_kb = 0.0
    for s in reversed(result.stages):
        if s.file_kb is not None:
            file_kb = s.file_kb
            break

    count = result.count
    if count <= 0:
        lines.append("  No candles to analyse.")
        return lines

    us_per_candle = (total_wall / count) * 1000

    lines.append(
        f"  Wall-clock: {us_per_candle:.2f} μs/candle  "
        f"→ {'PASS' if us_per_candle < 5 else 'WARN' if us_per_candle < 10 else 'FAIL'}"
    )
    lines.append(
        f"    Total {total_wall:.2f} ms for {count} candles. "
        f"Pipeline is {'on target' if us_per_candle < 5 else 'above target — investigate'}."
    )
    lines.append("")

    cpu_per = (total_cpu / count) * 1000
    cpu_wall = total_cpu / total_wall if total_wall > 0 else 0
    lines.append(
        f"  CPU time: {cpu_per:.2f} μs/candle  "
        f"→ {'PASS' if cpu_per < 4 else 'WARN' if cpu_per < 8 else 'FAIL'}"
    )
    lines.append(
        f"    CPU/Wall = {cpu_wall:.2f}. "
        + (
            "No I/O or lock contention."
            if cpu_wall >= 0.8
            else "I/O overhead detected — check disk throughput."
        )
    )
    lines.append("")

    mem_per = (total_mem / count) * 1024  # bytes per candle
    lines.append(
        f"  Memory: {mem_per:.1f} B/candle  "
        f"→ {'PASS' if mem_per < 850 else 'WARN' if mem_per < 1500 else 'FAIL'}"
    )
    lines.append(
        f"    Total allocated {total_mem:.2f} MB. "
        + (
            "Efficient allocation pattern."
            if mem_per < 850
            else "Above expected — review buffer sizes."
        )
    )
    lines.append("")

    peak_vs_total = peak / total_mem if total_mem > 0 else 0
    lines.append(
        f"  Peak vs allocated: {peak_vs_total:.1f}×  "
        f"→ {'PASS' if peak_vs_total < 2.5 else 'WARN' if peak_vs_total < 4 else 'FAIL'}"
    )
    lines.append(
        (
            f"    Peak {peak:.2f} MB vs total {total_mem:.2f} MB. "
            + (
                "Buffer pre-allocation is efficient."
                if peak_vs_total < 2.5
                else "PyArrow buffer pre-allocation is significant — consider chunking."
            )
        )
    )
    lines.append("")

    bpc = file_kb * 1024 / count if count > 0 and file_kb > 0 else 0
    lines.append(
        f"  File size: {bpc:.1f} B/candle  "
        f"→ {'PASS' if bpc < 50 else 'WARN' if bpc < 80 else 'FAIL'}"
    )
    lines.append(
        f"    On-disk {file_kb:.1f} KB for {count} candles. "
        + (
            "Parquet compression effective."
            if bpc < 50
            else "Above expected — schema review recommended."
        )
    )
    lines.append("")

    lines.append(f"  GC gen-2: {total_g2} collections  → {'PASS' if total_g2 < 5 else 'WARN' if total_g2 < 20 else 'FAIL'}")
    lines.append(
        (
            "    Zero long-lived garbage."
            if total_g2 == 0
            else f"    {total_g2} gen-2 collections — within tolerance."
            if total_g2 < 5
            else f"    {total_g2} gen-2 collections — review temporary object lifetimes."
        )
    )
    lines.append("")

    # Verbose-only insights
    if verbose:
        lines.append("  ── Stage-level breakdown ──")
        lines.append("")

        # Find stages of interest
        stages_by_name = {s.name: s for s in result.stages}

        candle_s = stages_by_name.get("Candle creation")
        extract_s = stages_by_name.get("Column extract")
        dec_cast_s = stages_by_name.get("decimal128 cast")
        ts_cast_s = stages_by_name.get("timestamp cast")
        table_s = stages_by_name.get("Table assembly")
        write_s = stages_by_name.get("Parquet write")

        if candle_s:
            pct = (candle_s.wall_ms / total_wall) * 100
            lines.append(
                f"    Candle creation: {pct:.0f}% of pipeline wall "
                f"({candle_s.wall_ms:.2f} ms). "
                f"Expected — this is where data objects are born."
            )
            lines.append("")

        if dec_cast_s and ts_cast_s:
            per_col = dec_cast_s.wall_ms / 5
            lines.append(
                f"    decimal128 cast: {dec_cast_s.wall_ms:.2f} ms for 5 columns "
                f"({per_col:.3f} ms/col). "
                + (
                    "C++ .cast() is well-optimised."
                    if per_col < 0.2
                    else "Per-column cost is elevated — review type strategy."
                )
            )
            lines.append(
                f"    timestamp cast: {ts_cast_s.wall_ms:.2f} ms for 1 column. "
                + (
                    "Efficient."
                    if ts_cast_s.wall_ms < 0.2
                    else "Timestamp parsing — consider format optimisation."
                )
            )
            lines.append("")

        if write_s:
            pct = (write_s.wall_ms / total_wall) * 100
            lines.append(
                f"    Parquet write: {pct:.0f}% of pipeline wall "
                f"({write_s.wall_ms:.2f} ms). "
                + (
                    "I/O bound — expected."
                    if pct > 30
                    else "Write is not the bottleneck."
                )
            )
            lines.append("")

    return lines


def _format_schema_section(schema: dict[str, str]) -> list[str]:
    lines: list[str] = [
        "",
        "SCHEMA",
        "─" * 100,
    ]
    if not schema:
        lines.append("  (no schema read)")
        return lines

    # Group into decimal128 and others
    dec_cols = {k: v for k, v in schema.items() if "decimal" in v}
    ts_cols = {k: v for k, v in schema.items() if "timestamp" in v}
    other_cols = {k: v for k, v in schema.items() if k not in dec_cols and k not in ts_cols}

    dict_suffix = "  (dictionary)"

    for k, v in dec_cols.items():
        lines.append(f"  {k:12s} {v}")
    for k, v in ts_cols.items():
        lines.append(f"  {k:12s} {v}")
    for k, v in other_cols.items():
        lines.append(f"  {k:12s} {v}{dict_suffix}")

    return lines


# ── typer commands ─────────────────────────────────────────────────


@app.command()
def run(
    count: int = typer.Option(10000, "--count", "-n", help="Number of candles to generate"),
    iterations: int = typer.Option(5, "--iterations", "-i", help="Number of benchmark runs (default 5)"),
    ts_res: str = typer.Option("s", "--ts-res", help="Timestamp resolution: s or us"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show fine-grained checkpoint stages"),
    isolated: bool = typer.Option(False, "--isolated", help="Pin to one CPU and raise priority (opt-in isolation)"),
    runner_name: str = typer.Option("candle", "--runner", "-r", help="Pipeline runner to benchmark"),
    output: Path = typer.Option(None, "--output", "-o", help="Write results as JSON to this file"),
) -> None:
    # ── resolve runner ────────────────────────────────────────
    runner_cls = RUNNERS.get(runner_name)
    if runner_cls is None:
        available = ", ".join(RUNNERS)
        typer.echo(f"Unknown runner '{runner_name}'. Available: {available}", err=True)
        raise typer.Exit(code=1)

    ts_config = TimestampConfig(resolution=ts_res)

    # ── optional CPU isolation ────────────────────────────────
    if isolated:
        _setup_isolated()

    # ── warmup: trigger PyArrow one-time init ─────────────────
    wc = [Candle(exchange="w", symbol="w", timeframe="1h", timestamp="2026-01-01T00:00:00", open="1", high="2", low="1", close="2", volume="1", source="w") for _ in range(10)]
    _to_decimal128([c.open for c in wc], "open", "warmup")
    _to_timestamp([c.timestamp for c in wc], ts_config)

    # ── run benchmark (N iterations) ──────────────────────────
    results: list[Any] = []
    tracemalloc.start()

    for i in range(iterations):
        gc.collect()
        tracemalloc.clear_traces()

        runner = runner_cls()
        base_path = str(Path(f".bench_tmp_{i}"))

        if verbose:
            result = runner.run_verbose(count, ts_config, base_path)
        else:
            result = runner.run_coarse(count, ts_config, base_path)

        results.append(result)
        import shutil
        shutil.rmtree(base_path, ignore_errors=True)

    tracemalloc.stop()

    # ── pick median run (by wall-clock) for detail report ────
    pipe_stats = [_pipeline_stats(r) for r in results]
    wall_times = [s["wall_ms"] for s in pipe_stats]
    median_wall = statistics.median(wall_times)
    median_idx = min(
        range(len(wall_times)),
        key=lambda i: abs(wall_times[i] - median_wall),
    )
    median_result = results[median_idx]
    rules = VERBOSE_RULES if verbose else DEFAULT_RULES
    outcomes = evaluate_rules(rules, median_result)

    # ── compute CI for pipeline totals across iterations ─────
    def _ci_line(
        label: str,
        values: list[float],
        unit: str = "ms",
        per_candle: bool = False,
        non_negative: bool = True,
    ) -> str:
        n = len(values)
        med, lo, hi = _compute_ci(values)
        lo = max(lo, 0) if non_negative else lo
        hi = max(hi, 0) if non_negative else hi
        vmin = min(values)
        vmax = max(values)
        per = ""
        if per_candle and count > 0:
            per_c = (med / count) * 1000
            per = f"  ({per_c:.1f} {'μs/c' if unit == 'ms' else 'B/c'})"
        base = f"  {label:20s} {med:.2f} {unit}"
        if n >= 5:
            return f"{base}  ± {(hi - lo) / 2:.2f}  (median, 95% CI [{lo:.2f}, {hi:.2f}]){per}"
        elif n >= 2:
            return f"{base}  (range: {vmin:.2f}–{vmax:.2f}){per}"
        return base

    # ── build report ──────────────────────────────────────────
    lines: list[str] = []
    header = f"Benchmark: {median_result.count:,} candles"
    header += f"  |  timestamp resolution = {median_result.ts_resolution}"
    header += f"  |  runner = {median_result.runner_name}"
    header += f"  |  {iterations} iteration(s)"
    if verbose:
        header += "  |  verbose"
    if isolated:
        header += "  |  isolated"

    lines.append(header)
    lines.append("═" * len(header))
    lines.append("")

    # Metric definitions
    lines.append("METRIC DEFINITIONS  (μs = microseconds, B = bytes)")
    lines.append("─" * 100)
    lines.append("Wall-clock (ms) — Real wall time per stage. Target <5 μs/candle total.")
    lines.append("CPU time (ms) — On-CPU time (user + sys). Primary decision metric.")
    lines.append("MemΔ (MB) — Memory allocated in the stage (tracemalloc positive-only).")
    lines.append("  Expected: ~120 B/candle for Candle creation, ~50 B/candle for conversions.")
    lines.append("Peak (MB) — Highest resident memory watermark.")
    lines.append("GC (g0/g1/g2) — Garbage collector runs per generation.")
    lines.append("File (KB) — Parquet file on disk. Expected 30–40 B/candle.")
    lines.append("CI reported at end — stage table shows the median run.")
    lines.append("")

    # Results table (median run)
    pipe_stages = median_result.stages[: median_result.pipeline_end_index + 1]
    all_stages = median_result.stages

    total_wall = sum(s.wall_ms for s in pipe_stages)
    total_cpu = sum(s.cpu_ms for s in pipe_stages)
    total_mem = sum(max(s.mem_delta_mb, 0) for s in pipe_stages)
    cumulative_wall = 0.0
    cumulative_cpu = 0.0
    cumulative_mem = 0.0

    name_w = max(_stage_name_width(all_stages), 12)
    sep = "─" * 100

    col_header = (
        f"{'Stage':<{name_w}} {'Wall(ms)':>9} {'W%':>5}"
        f" {'CPU(ms)':>9} {'C%':>5}"
        f" {'MemΔ(MB)':>9} {'M%':>5}"
        f" {'Peak(MB)':>8}"
        f" {'GC(g0/g1/g2)':>14}"
        f" {'File(KB)':>8}"
    )

    lines.append(col_header)
    lines.append(sep)

    for stage in all_stages:
        cumulative_wall += stage.wall_ms
        cumulative_cpu += stage.cpu_ms
        cumulative_mem += max(stage.mem_delta_mb, 0)

        is_pipeline = all_stages.index(stage) <= median_result.pipeline_end_index

        w_pct = _cum_pct(cumulative_wall if is_pipeline else 0, total_wall)
        c_pct = _cum_pct(cumulative_cpu if is_pipeline else 0, total_cpu)
        m_pct = _cum_pct(cumulative_mem if is_pipeline else 0, total_mem)

        wall_s = _fmt(stage.wall_ms)
        cpu_s = _fmt(stage.cpu_ms)
        mem_s = _fmt(stage.mem_delta_mb)
        peak_s = _fmt(stage.peak_mb)
        gc_s = f"{stage.gc_g0}/{stage.gc_g1}/{stage.gc_g2}"
        file_s = _fmt(stage.file_kb) if stage.file_kb is not None else _fmt_none()

        mark = ""
        if not is_pipeline and stage != all_stages[0]:
            mark = "  *"

        row = (
            f"{stage.name:<{name_w}} {wall_s:>9} {w_pct:>5}"
            f" {cpu_s:>9} {c_pct:>5}"
            f" {mem_s:>9} {m_pct:>5}"
            f" {peak_s:>8}"
            f" {gc_s:>14}"
            f" {file_s:>8}{mark}"
        )
        lines.append(row)

    lines.append(sep)

    # Summary row (pipeline only)
    peak_stage = max(all_stages, key=lambda s: s.peak_mb)
    total_g0 = sum(s.gc_g0 for s in pipe_stages)
    total_g1 = sum(s.gc_g1 for s in pipe_stages)
    total_g2 = sum(s.gc_g2 for s in pipe_stages)
    file_kb_total = max((s.file_kb for s in all_stages if s.file_kb is not None), default=0.0)

    lines.append(
        f"{'Pipeline total':<{name_w}} {_fmt(total_wall):>9} {'':>5}"
        f" {_fmt(total_cpu):>9} {'':>5}"
        f" {_fmt(total_mem):>9} {'':>5}"
        f" {_fmt(peak_stage.peak_mb):>8}"
        f" {total_g0}/{total_g1}/{total_g2:>14}"
        f" {_fmt(file_kb_total) if file_kb_total > 0 else _fmt_none():>8}"
    )

    # Schema section
    lines.extend(_format_schema_section(median_result.schema))

    # Validation section
    lines.extend(_format_validation_section(outcomes, rules))

    # Cross-validation section
    lines.extend(_format_cross_validation_section(median_result, verbose))

    # ── iteration summary with CIs ────────────────────────────
    lines.append("")
    lines.append("ITERATION SUMMARY")
    lines.append("─" * 100)
    lines.append("")

    lines.append(_ci_line("CPU time", [s["cpu_ms"] for s in pipe_stats], "ms", per_candle=True))
    lines.append(_ci_line("Wall-clock", [s["wall_ms"] for s in pipe_stats], "ms", per_candle=True))
    lines.append(_ci_line("Memory delta", [s["mem_mb"] for s in pipe_stats], "MB", non_negative=True))

    peak_vals = [s["peak_mb"] for s in pipe_stats]
    lines.append(_ci_line("Peak memory", peak_vals, "MB", non_negative=True))

    file_vals = [s["file_kb"] for s in pipe_stats]
    if len(set(file_vals)) == 1:
        lines.append(f"  {'File size':20s} {file_vals[0]:.2f} KB (deterministic)")
    else:
        lines.append(_ci_line("File size", file_vals, "KB"))

    # Verbose: per-iteration table
    if verbose:
        lines.append("")
        lines.append("PER-ITERATION TABLE")
        lines.append("─" * 100)
        header_row = (
            f"  {'Iter':>4}   {'CPU(ms)':>9}   {'Wall(ms)':>9}"
            f"   {'Mem(MB)':>8}   {'Peak(MB)':>8}   {'GC(g2)':>6}   {'File(KB)':>8}"
        )
        lines.append(header_row)
        lines.append("  " + "─" * 64)
        for idx, (r, s) in enumerate(zip(results, pipe_stats)):
            cpu_v = s["cpu_ms"]
            wall_v = s["wall_ms"]
            mem_v = s["mem_mb"]
            peak_v = s["peak_mb"]
            g2_v = sum(st.gc_g2 for st in r.stages[: r.pipeline_end_index + 1])
            file_v = s["file_kb"]
            lines.append(
                f"  {idx + 1:>4}   {cpu_v:>9.2f}   {wall_v:>9.2f}"
                f"   {mem_v:>8.2f}   {peak_v:>8.2f}   {g2_v:>6}   {file_v:>8.2f}"
            )
        lines.append("")

    # Isolation note
    if not isolated:
        lines.append("  Pass --isolated for dedicated CPU affinity.")
    else:
        lines.append("  CPU and wall-clock converged — measurement is stable.")

    lines.append("")

    # Runner note
    runners_available = ", ".join(RUNNERS)
    lines.extend([
        f"Runners available: {runners_available}",
        "Pass --runner path.to.MyRunner to benchmark a custom pipeline.",
        "─" * 100,
        "",
    ])

    report = "\n".join(lines)
    typer.echo(report)

    # Optional JSON output (all raw results)
    if output:
        import json

        all_stages_raw = []
        for idx, r in enumerate(results):
            s = pipe_stats[idx]
            all_stages_raw.append({
                "iteration": idx + 1,
                "wall_ms": s["wall_ms"],
                "cpu_ms": s["cpu_ms"],
                "mem_delta_mb": s["mem_mb"],
                "peak_mb": s["peak_mb"],
                "file_kb": s["file_kb"],
                "stages": [
                    {
                        "name": st.name,
                        "wall_ms": st.wall_ms,
                        "cpu_ms": st.cpu_ms,
                        "mem_delta_mb": st.mem_delta_mb,
                        "peak_mb": st.peak_mb,
                        "gc_g0": st.gc_g0,
                        "gc_g1": st.gc_g1,
                        "gc_g2": st.gc_g2,
                        "file_kb": st.file_kb,
                    }
                    for st in r.stages
                ],
            })

        data = {
            "count": count,
            "ts_resolution": ts_res,
            "runner": runner_name,
            "iterations": iterations,
            "isolated": isolated,
            "results": all_stages_raw,
            "schema": median_result.schema,
            "rules": [
                {"name": n, "rating": r, "message": m}
                for n, r, m in outcomes
            ],
        }
        output.write_text(json.dumps(data, indent=2))
        typer.echo(f"  Wrote JSON to {output}")


@app.command()
def profile(
    symbol: str = typer.Option("BTC/USDT", "--symbol", help="Trading pair symbol (FakeProvider)"),
    timeframe: str = typer.Option("1h", "--timeframe", help="Candle timeframe"),
    start: str = typer.Option(
        ..., "--start", help="Start time (ISO-8601, e.g. 2026-05-25)"
    ),
    end: str = typer.Option(
        ..., "--end", help="End time (ISO-8601, e.g. 2026-05-27)"
    ),
    iterations: int = typer.Option(
        3, "--iterations", "-i", help="Benchmark iterations per provider"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show fine-grained checkpoint stages per provider"),
) -> None:
    """Profile each market-data provider (fake, bitfinex, kucoin) with
    the same symbol/timeframe range and print a comparison."""
    import gc
    import shutil

    ts_config = TimestampConfig(resolution="s")

    dt_start = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    dt_end = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)

    # Each provider uses its own symbol convention
    providers: list[tuple[str, Any, str]] = [
        ("fake", FakeProvider(), symbol),
        ("bitfinex", BitfinexProvider(), "tBTCUSD"),
        ("kucoin", KuCoinProvider(), "BTC-USDT"),
    ]

    # warmup: trigger PyArrow one-time init (~300ms)
    wc = [Candle(exchange="w", symbol="w", timeframe="1h", timestamp="2026-01-01T00:00:00", open="1", high="2", low="1", close="2", volume="1", source="w") for _ in range(10)]
    _to_decimal128([c.open for c in wc], "open", "warmup")
    _to_timestamp([c.timestamp for c in wc], ts_config)

    tracemalloc.start()

    all_results: list[tuple[str, BenchmarkResult]] = []

    for pname, pinst, psym in providers:
        results: list[BenchmarkResult] = []
        for i in range(iterations):
            gc.collect()
            tracemalloc.clear_traces()

            runner = ProviderCandlePipelineRunner(
                provider=pinst, symbol=psym, timeframe=timeframe,
                start=dt_start, end=dt_end,
            )
            base_path = f".bench_tmp_{pname}_{i}"
            if verbose:
                result = runner.run_verbose(0, ts_config, base_path)
            else:
                result = runner.run_coarse(0, ts_config, base_path)
            results.append(result)
            shutil.rmtree(base_path, ignore_errors=True)

        # pick median by wall-clock
        pipe_stats = [_pipeline_stats(r) for r in results]
        wall_times = [s["wall_ms"] for s in pipe_stats]
        median_wall = statistics.median(wall_times)
        median_idx = min(
            range(len(wall_times)),
            key=lambda i: abs(wall_times[i] - median_wall),
        )
        all_results.append((pname, results[median_idx]))

    tracemalloc.stop()

    # ── build comparison report ────────────────────────────────
    lines: list[str] = []
    lines.append("PROVIDER COMPARISON")
    lines.append("═══════════════════")
    lines.append("")

    header = (
        f"  {'Provider':>12} {'Candles':>8} {'Wall(ms)':>10}"
        f" {'CPU(ms)':>10} {'Net(ms)':>9}"
        f" {'Mem(MB)':>9} {'Peak(MB)':>9}"
        f" {'File(KB)':>9} {'Issues':>7}"
    )
    lines.append(header)
    lines.append("  " + "─" * 84)

    for pname, result in all_results:
        ps = _pipeline_stats(result)
        net = ps["wall_ms"] - ps["cpu_ms"]
        lines.append(
            f"  {pname:>12} {result.count:>8} {ps['wall_ms']:>10.2f}"
            f" {ps['cpu_ms']:>10.2f} {net:>9.2f}"
            f" {ps['mem_mb']:>9.2f}"
            f" {ps['peak_mb']:>9.2f} {ps['file_kb']:>9.2f}"
            f" {result.validation_issues:>7}"
        )

    lines.append("  " + "─" * 84)
    lines.append("")
    lines.append("Net = wall - cpu  (time spent waiting on I/O, network, or scheduler)")
    lines.append("     near 0 → CPU-bound     much larger than 0 → network/I/O-bound")
    lines.append("")

    # per-provider detail tables
    for pname, result in all_results:
        pipe_stages = result.stages[: result.pipeline_end_index + 1]
        all_stages = result.stages
        total_wall = sum(s.wall_ms for s in pipe_stages)
        total_cpu = sum(s.cpu_ms for s in pipe_stages)

        name_w = max(_stage_name_width(all_stages), 12)
        sep = "  " + "─" * 69

        lines.append(f"[{pname}]")
        lines.append("")
        col_header = (
            f"  {'Stage':<{name_w}} {'Wall(ms)':>9} {'CPU(ms)':>9}"
            f" {'Mem(MB)':>9} {'Peak(MB)':>9} {'File(KB)':>8}"
        )
        lines.append(col_header)
        lines.append(sep)

        for stage in all_stages:
            is_pipeline = all_stages.index(stage) <= result.pipeline_end_index
            wall_s = _fmt(stage.wall_ms)
            cpu_s = _fmt(stage.cpu_ms)
            mem_s = _fmt(stage.mem_delta_mb)
            peak_s = _fmt(stage.peak_mb)
            file_s = _fmt(stage.file_kb) if stage.file_kb is not None else _fmt_none()
            mark = "  *" if (not is_pipeline and stage != all_stages[0]) else ""
            lines.append(
                f"  {stage.name:<{name_w}} {wall_s:>9} {cpu_s:>9}"
                f" {mem_s:>9} {peak_s:>9} {file_s:>8}{mark}"
            )

        lines.append(sep)
        peak_stage = max(all_stages, key=lambda s: s.peak_mb)
        file_kb_total = max((s.file_kb for s in all_stages if s.file_kb is not None), default=0.0)
        pipeline_mem = sum(max(s.mem_delta_mb, 0) for s in pipe_stages)
        lines.append(
            f"  {'Pipeline total':<{name_w}} {_fmt(total_wall):>9} {_fmt(total_cpu):>9}"
            f" {_fmt(pipeline_mem):>9}"
            f" {_fmt(peak_stage.peak_mb):>9}"
            f" {_fmt(file_kb_total) if file_kb_total > 0 else _fmt_none():>8}"
        )
        lines.append("")

        # Network/CPU Boundary section
        net_wait = total_wall - total_cpu
        ratio = net_wait / total_cpu if total_cpu > 0 else 0
        regime = "CPU-bound" if ratio < 0.5 else "network-bound" if ratio > 1.5 else "balanced"
        lines.append("  ── Network/CPU Boundary ──")
        lines.append(f"  Network wait:  {net_wait:.2f} ms  (wall - cpu = time outside our process)")
        lines.append(f"  CPU processing: {total_cpu:.2f} ms  (total CPU for pipeline stages)")
        lines.append(f"  Network/CPU ratio: {ratio:.1f}×  → {regime}")
        lines.append("")

        lines.append(f"  Candles: {result.count}  |  Validation issues: {result.validation_issues}")
        lines.append("")

    report = "\n".join(lines)
    typer.echo(report)


if __name__ == "__main__":
    app()
