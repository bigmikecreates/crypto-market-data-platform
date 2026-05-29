# Benchmark Design

## What it measures

The benchmark pipeline measures the end-to-end cost of converting raw market
data into validated, stored Parquet files. It reports wall-clock time, CPU
time, memory delta, peak memory, GC pressure, and file size per stage.

## Two measurement modes

| Mode | Flag | Mechanism | What it reveals |
|------|------|-----------|-----------------|
| Default | *(none)* | Shared core, normal priority, scheduler interference expected | Real-world performance — includes unavoidable OS noise |
| Isolated | `--isolated` | `sched_setaffinity` to one logical core + `nice(-10)` | Ceiling performance — pipeline's inherent cost in near-ideal isolation |

The gap between the two is itself a signal. A wide gap means the pipeline is
scheduler-sensitive. A narrow gap means the code already runs efficiently
under real-world conditions.

## Two benchmark paths

### `run` — synthetic (CPU-bound)

Creates `Candle` objects in-process (no network), runs validation, writes
Parquet. Measures local pipeline overhead.

### `profile` — live provider (network-bound)

Fetches real data from a live exchange API, then runs the same validation
and write pipeline. Measures end-to-end ingestion cost including HTTP
round-trips.

→ See [Python API Reference](reference/python-api.md) for the exact benchmark
runner signatures and command-line arguments.

## Network/CPU boundary

The `profile` command reports a **Network/CPU boundary** section showing
network wait time, CPU processing time, and a ratio that classifies the
bottleneck regime (CPU-bound, balanced, or network-bound).

## Fixed-iteration strategy

Default `N=5`, user-configurable via `--iterations`. Never adaptive — fixed N
gives predictable execution cost. A 95 % confidence interval is computed using
Student's t-distribution.

## Cross-validation rules

The benchmark applies 7 cross-validation rules to detect anomalies (compression
ratio, CPU/Wall ratio, GC pressure, write dominance, memory allocation patterns,
validation overhead, column conversion cost).

## Baseline metrics

The current bottleneck is `Candle` dataclass construction. For real-world
usage, API latency and rate limits dominate — local pipeline overhead is
negligible in that context.

→ See [Performance Notes](performance-notes.md) for the exact baseline metrics
and live provider profiles.
