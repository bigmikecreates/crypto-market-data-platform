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

```bash
python scripts/benchmark_pipeline.py --count 10000
```

Creates `Candle` objects in-process (no network), runs validation, writes
Parquet. This measures the local pipeline overhead: object construction,
decimal128 casting, validation, file I/O.

### `profile` — live provider (network-bound)

```bash
python scripts/benchmark_pipeline.py profile --provider bitfinex
```

Fetches real data from a live exchange API, then runs the same validation
and write pipeline. This measures end-to-end ingestion cost including HTTP
round-trips.

## Network/CPU boundary

The `profile` command reports a **Network/CPU boundary** section:

```
Network wait:  63.95 ms  (wall − cpu = time outside our process)
CPU processing: 11.31 ms  (total CPU for pipeline stages)
Network/CPU ratio: 5.7×  → network-bound
```

The ratio classifies the bottleneck regime:

| Ratio | Classification | What to optimise |
|-------|---------------|------------------|
| `< 0.5` | CPU-bound | Object creation, casting, validation throughput |
| `0.5 – 1.5` | Balanced | Either domain |
| `> 1.5` | Network-bound | Batch sizes, parallel fetching, connection reuse |

## Fixed-iteration strategy

Default `N=5`, user-configurable via `--iterations`. Never adaptive — adaptive
or run-until-stable strategies hide resource consumption and produce unbounded
execution time. Fixed N gives predictable cost.

A 95 % confidence interval is computed using Student's t-distribution (df =
N-1), with the median as the point estimate:

```
Pipeline CPU time (5 runs): 18.3 ms ± 0.3 ms (median, 95% CI [17.9, 18.7])
```

## Cross-validation rules

The benchmark applies 7 cross-validation rules to detect anomalies:

1. **Compression ratio** — warn if file size per candle is outside
   0.5–100 B/c range
2. **CPU/Wall ratio** — flag if below 0.8 (signals preemption or I/O
   contention)
3. **GC gen-2 collections** — warn if any gen-2 collections occurred
4. **Parquet write dominance** — flag if writing takes > 90 % of pipeline CPU
5. **Peak vs total allocated** — flag if peak memory far exceeds per-stage
   deltas
6. **Validation overhead** (verbose) — warn if validation takes > 20 % of
   pipeline CPU
7. **Column conversion cost** (verbose) — flag individual columns that
   dominate conversion time

## Baseline metrics

| Metric | 100 candles | 10,000 candles |
|--------|-------------|----------------|
| Wall-clock | 8.32 ms (83 μs/c) | 208 ms (21 μs/c) |
| CPU/Wall | 0.98 | 0.98 |
| Peak memory | 0.54 MB | 3.81 MB |
| File size | 6.4 KB (65 B/c) | 20.8 KB (2.1 B/c) |
| GC gen-2 | 0 | 0 |
| Bottleneck | Candle creation (22 %) | Candle creation (61 %) |

The current bottleneck is `Candle` dataclass construction. For real-world
usage, API latency and rate limits dominate — local pipeline overhead (~20 μs
per candle) is negligible in that context.
