# Performance Notes

## Current known characteristics

### Local pipeline (synthetic benchmark)

At 10,000 candles, the local pipeline (Candle creation → validation → Parquet
write) shows:

| Metric | Value | Note |
|--------|-------|------|
| Throughput | ~48,000 candles/s | 208 ms for 10k candles, single-threaded |
| CPU efficiency | 98 % | Wall-clock ≈ CPU time — minimal I/O wait |
| Memory per candle | ~381 B | String fields + `slots=True` dataclass overhead |
| Storage per candle | ~2.1 B | With Parquet dictionary compression on string columns |
| Bottleneck | Candle construction | ~61 % of pipeline CPU at 10k |

The bottleneck is `Candle` dataclass creation, not decimal128 casting or
Parquet writing. For real workloads, API latency dominates — the local
pipeline overhead is negligible.

### Live provider profiles

| Provider | Candles | Wall (ms) | CPU (ms) | Net (ms) | Net/CPU | Regime |
|----------|---------|-----------|---------|----------|---------|--------|
| Synthetic | 10,000 | 154.6 | 161.1 | −6.5 | −0.0× | CPU-bound |
| Bitfinex | 24 | 75.3 | 11.3 | 64.0 | 5.7× | Network-bound |
| KuCoin | 24 | 280.7 | 9.0 | 271.7 | 30.1× | Network-bound |

Key insight: a 10× improvement in local pipeline throughput would reduce
synthetic time by 90 %, but would reduce Bitfinex ingestion by ~15 % and
KuCoin ingestion by ~3 %. The optimisation lever changes entirely once
network I/O is in play.

## How to interpret benchmark tables

```
Pipeline CPU time (5 runs): 18.3 ms ± 0.3 ms (median, 95% CI [17.9, 18.7])
                                                     └─────────┬─────────┘
                                                    Tight CI = stable measurement
```

- **CPU time** is the decision metric — it counts only cycles our thread
  actually ran, making it deterministic per-operation.
- **Wall-clock** is secondary — it reflects real-world wait time including
  scheduler artifacts.
- **CI width** is a self-calibrating trust indicator: tight CI on CPU time
  at N=5 means you can make optimisation decisions confidently.
- **CPU/Wall ratio below 0.8** signals preemption or I/O contention — the
  measurement environment was busy.

## Known caveats

- `tracemalloc` tracks only Python-side allocations, not PyArrow's C-level
  buffer allocations — peak memory numbers under-report total RSS
- `pq.read_schema` may display `timestamp[ms]` even when written as
  `timestamp[s]` (PyArrow converts to ms for Parquet storage)
- Benchmark data has limited cardinality in string columns — Parquet
  dictionary compression can make file size appear unrealistically small
  vs varied real data
- First `pa.array()` call in a process incurs ~300 ms PyArrow init overhead
  (mitigated by warmup in benchmark runner)
