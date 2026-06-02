# Benchmarking

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

→ See [Python API Reference](/crypto-market-data-platform/reference/#/python-api) for the exact benchmark
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

## Measured baseline — local I/O pipeline

All measurements use `python scripts/benchmark_pipeline.py run --count 10000
--iterations 10 --verbose` on a shared core (no `--isolated`). Median iteration
selected as the representative run; 95% CI via Student's t-distribution (df=9).

```
Benchmark: 10,000 candles  |  timestamp resolution = s  |  runner = candle  |  10 iterations

CPU time    209.93 ms  ±21.75  (median, 95% CI [182.62, 226.13])  — 21.0 μs/candle
Wall-clock  210.03 ms  ±21.79  (median, 95% CI [182.64, 226.23])  — 21.0 μs/candle
Memory      4.62 MB  (deterministic across all iterations)
Peak        3.81 MB  (deterministic)
File size   20.81 KB  (deterministic, 2.1 B/candle with dictionary compression)
GC gen-2    0 collections
CPU/Wall    1.00  (pure CPU-bound — no I/O or scheduler contention)
```

**Stage breakdown (median run):**

| Stage | Wall (ms) | % of pipeline |
|-------|-----------|---------------|
| Candle creation | 141 ms | 69% |
| decimal128 cast (5 cols) | 49 ms | 24% |
| Column extract + table assembly | 7 ms | 3% |
| Parquet write | 8 ms | 4% |
| timestamp cast | 0.5 ms | <1% |

The bottleneck is `Candle` dataclass construction, not Parquet writing.

## Before/after comparison — network optimizations (Options A and C)

Options A (connection pooling) and C (concurrent symbol fetching) were applied
after the baseline run. The post-optimization synthetic benchmark is unchanged:

```
Baseline  (before A + C): median 210 ms, 95% CI [183, 226] ms
Post-opt  (after  A + C): median 224 ms, 95% CI [178, 380] ms
```

The medians are statistically equivalent. **This is the correct result.** The
synthetic benchmark uses `CandlePipelineRunner`, which generates `Candle` objects
in-process without any HTTP calls. A connection pooling change cannot affect it.
The wider CI in the post-optimization run reflects OS scheduling jitter during
that run (two iterations at ~550 ms), not a regression. The median correctly
excludes these from the headline number.

**Impact of Options A and C appears only in `profile` runs against real providers.**

→ See [Design Rationale §11](benchmarks/design-rationale.md) for the full analysis
of what each option does, why Option B (concurrent page fetching) is overengineering,
and the reasoning behind the median + CI averaging strategy.

## Live provider profiles

A 10× improvement in local pipeline throughput reduces synthetic time by 90%,
but reduces Bitfinex ingestion by ~15% and KuCoin ingestion by ~3%.

| Provider | Candles | Wall (ms) | CPU (ms) | Net (ms) | Net/CPU | Regime |
|----------|---------|-----------|----------|----------|---------|--------|
| Synthetic (CandlePipelineRunner) | 10,000 | 210 | 210 | ~0 | ~0x | CPU-bound |
| FakeProvider | 1 | ~2 | ~2 | <0.2 | 0.1x | CPU-bound |
| BitfinexProvider | 24 | ~75 | ~11 | ~64 | 5.7x | Network-bound |
| KuCoinProvider | 24 | ~281 | ~9 | ~272 | 30x | Network-bound |

Net = wall - cpu: time spent outside our process waiting on HTTP, scheduler, or I/O.
A negative Net for the synthetic run is timer granularity noise — effectively zero.

**What this means for optimization:** For network-bound providers, a 50% improvement
in local pipeline throughput saves ~5 ms out of ~75 ms (Bitfinex) or ~4 ms out of
~281 ms (KuCoin). The returns are rapidly diminishing. The correct lever is
reducing HTTP round-trips (larger page sizes, connection reuse) or parallelizing
across symbols (Option C).

## How to interpret benchmark output

```
Pipeline CPU time (10 runs): 209.93 ms ± 21.75 ms (median, 95% CI [182.62, 226.13])
                                                              └──────────────┬───────────┘
                                                  Tight CI = stable environment
                                                  Wide CI = noisy environment, run --isolated
```

- **CPU time** is the decision metric — counts only cycles our thread actually ran.
  It is deterministic per-operation and low-noise.
- **Wall-clock** is secondary — includes real-world scheduler artifacts and I/O wait.
- **CPU/Wall ratio**: below 0.8 signals preemption or I/O contention.
- **CI width** is a self-calibrating trust indicator. A tight CI on CPU time at
  N=5 means you can make optimisation decisions confidently. A wide CI on wall-clock
  means the environment was noisy — use `--isolated`.
- **Median (not mean)** is the headline because single GC-pause or OS-scheduling
  outliers inflate the mean without representing steady-state cost.

## Known caveats

- `tracemalloc` tracks only Python-side allocations, not PyArrow's C-level
  buffer allocations — peak memory numbers under-report total RSS.
- `pq.read_schema` may display `timestamp[ms]` even when written as `timestamp[s]`
  (PyArrow converts to ms for Parquet storage internally).
- Benchmark data has limited cardinality in string columns — Parquet dictionary
  compression makes file size appear smaller than varied real data would produce.
- First `pa.array()` call in a process incurs ~300 ms PyArrow init overhead
  (mitigated by the warmup step in the benchmark runner).
- Benchmarks run without `--isolated` include OS scheduling jitter. Two outlier
  iterations at ~550 ms in the post-optimization run demonstrate this — the median
  correctly excluded them.
