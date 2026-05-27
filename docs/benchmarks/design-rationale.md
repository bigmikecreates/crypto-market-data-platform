# Design Rationale — Pipeline Architecture Decisions

> This document records the data-driven reasoning behind key architectural
> decisions in the market data pipeline. Each section states the decision,
> the rationale, and the benchmark evidence that supports it.

---

## 1. String fields over Python `Decimal` in `Candle` objects

**Decision:** Store `open`, `high`, `low`, `close`, `volume` as `str` in the
`Candle` dataclass rather than `Decimal`.

**Rationale:**
- `str` objects are lighter than `Decimal` objects (~50 B vs ~120 B per field).
- The values are converted to `decimal128(38, 10)` at write time via PyArrow's
  C++ `cast()` — no Python `Decimal` objects are created during the write path.
- Validation (regex match) operates on the string directly without creating
  intermediate objects.

**Benchmark evidence:**
```
python scripts/benchmark_pipeline.py --count 10000

Candle creation (10000 candles):
  Wall:  126.75 ms  (12.6 μs/candle)
  MemΔ:    3.81 MB  (381 B/candle)
  CPU:   123.84 ms

Decimal128 cast (5 columns):
  Wall:  ~1.28 ms for 100 candles  (0.256 ms/column)
  -- done via C++ .cast(), no Python Decimal objects created

File size on disk:
  20.8 KB for 10000 candles  (2.1 B/candle — with Parquet dictionary encoding)
```

The memory per candle (381 B for 10 string fields + dataclass overhead) is
significantly lower than the equivalent `Decimal`-based model (~900 B estimated).

---

## 2. C++ `.cast()` over Python `Decimal()` conversion

**Decision:** Convert strings to `decimal128` at the PyArrow level using
`pa.array(str_values).cast(pa.decimal128(38, 10))` rather than constructing
Python `Decimal()` objects and passing them to `pa.array()`.

**Rationale:**
- The `.cast()` operation runs in PyArrow's C++ compute layer — no Python
  `Decimal` objects are instantiated at any point in the pipeline.
- The cast is vectorised across the entire column in a single call.
- Results in zero Python `Decimal` overhead in the entire write path.

**Benchmark evidence:**
```
decimal128 cast (5 columns, 100 candles): 1.28 ms total → 0.256 ms/column
timestamp cast (1 column, 100 candles):   0.11 ms total → 0.110 ms/column

Pipeline total (100 candles): 8.32 ms → 83.2 μs/candle
Pipeline total (10000 candles): 208.04 ms → 20.8 μs/candle
```

The primary bottleneck is `Candle` object creation (61 % of pipeline wall time
at 10k candles), not the conversion step (which accounts for ~15 %).

---

## 3. `@dataclass(slots=True)` for `Candle`

**Decision:** Use `slots=True` to reduce per-instance memory overhead.

**Rationale:**
- `slots=True` eliminates the per-instance `__dict__` (~120 B saved per object).
- With 10 fields and potentially millions of candles in memory, this is a
  meaningful saving.
- The benchmark does not compare `slots=True` vs `slots=False` directly, but
  the per-candle memory measurement (381 B for 10 string fields) is consistent
  with slots-enabled dataclass overhead.

---

## 4. Fixed `decimal128(38, 10)` schema over dynamic precision

**Decision:** Use `decimal128(38, 10)` for all five numeric columns (open,
high, low, close, volume) regardless of ticker or price range.

**Rationale:**
- `decimal128` is always 16 bytes regardless of precision/scale — there is no
  storage benefit to using narrower types.
- A fixed schema guarantees that DuckDB `UNION` queries across tickers do not
  encounter type mismatches.
- The 38‑digit precision with 10 fractional digits covers all realistic crypto
  prices (from `0.0000000001` to `9999999999999999999999999999.9999999999`).

**Schema as written:**
```
open:      decimal128(38, 10)
high:      decimal128(38, 10)
low:       decimal128(38, 10)
close:     decimal128(38, 10)
volume:    decimal128(38, 10)
timestamp: timestamp[s]
exchange:  string  (dictionary)
symbol:    string  (dictionary)
timeframe: string  (dictionary)
source:    string  (dictionary)
```

---

## 5. Timestamp as string, resolved via `TimestampConfig`

**Decision:** Store `timestamp` as `str` in the `Candle` dataclass, with a
`TimestampConfig` class controlling resolution (`s` or `us`) at write time.

**Rationale:**
- Consistent with the "strings first" pattern used for numeric fields.
- The `TimestampConfig` class isolates the resolution choice in one place.
- Default resolution is `"s"` (`%Y-%m-%dT%H:%M:%S`), with `"us"` available
  for sub-second precision when needed. Both cost 8 bytes on disk.

---

## 6. Performance Analysis Methodology

### 6.1 Two Measurement Modes

| Mode | Flag | Environment | What it measures | Use case |
|---|---|---|---|---|
| **Default** | *(none)* | Shared core, normal priority, scheduler interference expected | Real-world performance — includes unavoidable OS noise | Development, CI, sanity checks |
| **Isolated** | `--isolated` | Dedicated core via `sched_setaffinity`, elevated priority via `nice(-10)` | Ceiling performance — pipeline code cost in near-ideal isolation | Capacity planning, regression detection, optimisation decisions |

The gap between the two is itself a signal. A wide gap means the pipeline is
scheduler-sensitive — worth investigating. A narrow gap means the code already
runs efficiently under real-world conditions.

### 6.2 Primary vs Secondary Metrics

CPU time is the **decision metric** — it counts only cycles our thread actually
ran, making it deterministic per-operation and low-noise. Wall-clock is
secondary — it reflects real-world wait time and includes scheduler artifacts,
answering "how long did I wait?" rather than "how much work did we do?"

The CPU/Wall ratio acts as a built-in noise detector. A ratio below 0.8 signals
preemption or I/O contention — the measurement environment was busy.

### 6.3 Fixed-Iteration Strategy + Confidence Intervals

Default N=5, user-specified via `--iterations`. Never adaptive — adaptive or
run-until-stable strategies hide resource consumption from the user and produce
unbounded execution time. Fixed N gives predictable cost, and the CI width
honestly communicates how trustworthy the number is. All N samples contribute
to the estimate — no outlier removal, no trimmed means, no discarded data.

A 95% confidence interval is computed using Student's t-distribution (df = N-1),
with the median as the point estimate. The CI width is a self-calibrating trust
indicator:

- **Tight CI on CPU time at N=5** — you can make optimisation decisions
  confidently without running more iterations.
- **Wide CI on wall-clock** — honestly reflects a noisy or contended
  environment. Run with `--isolated` if this matters.

Format:

```
Pipeline CPU time (5 runs): 18.3 ms ± 0.3 ms (median, 95% CI [17.9, 18.7])
```

### 6.4 The `--isolated` Mode

**Mechanism:**
- `os.sched_setaffinity(0, {cpu})` — pins the benchmark process to one logical
  core so the OS almost never schedules other work on that execution unit.
- `os.nice(-10)` — raises scheduling priority so the kernel prefers our thread
  when dispatching.
- Prints the equivalent `taskset -c <cpu> ...` command so the user can run
  externally if they prefer.
- Falls back gracefully — if `nice(-10)` fails (typical for unprivileged users),
  pinning still applies, priority stays at default, and a note is printed.
  The flag never fails outright from missing privileges.

**Why the isolated mode is better for analysis:**

On a shared core, scheduler ticks, page reclaim, and cross-process preemption
jitter both wall-clock and `process_time()` measurements. With `--isolated`,
wall-clock and CPU time converge — both confidence bands collapse. The remaining
variance comes almost entirely from PyArrow's internal allocation variance and
Python's GC jitter. This lets a developer compare two commits and trust that a
2% difference in CPU time is real rather than environmental noise.

**Security / privilege caveats:**

- `nice(-10)` requires `CAP_SYS_NICE` (Linux capability) or root. When
  unavailable, the tool continues with pinning only and prints a note — it does
  not fail.
- CPU pinning affects system responsiveness — other processes compete for
  remaining cores. In CI or shared environments this may degrade co-tenants.
- SMT / hyperthreading means a "dedicated" logical core still shares execution
  units with its sibling. For true isolation, the sibling must also be idle
  or the process must be pinned to a whole physical core.
- Hardware interrupts and kernel threads can still preempt on the pinned core.
  The only way to eliminate those is `isolcpus` at boot time, which is outside
  the tool's scope.

**If full priority isolation is needed**, run the tool under
`taskset -c <core>` externally using the command printed in the output. This
keeps the benchmark unprivileged while giving the user full control over
isolation — CPU isolation and priority elevation are OS-level resource
management decisions, not pipeline measurement logic. Baking them into the tool
means the tool must own a privilege boundary (`CAP_SYS_NICE`, potential root
execution, security audit surface) for functionality tangential to its core
purpose. External `taskset` keeps that boundary at the OS level where it
belongs — the user decides whether and how to isolate, the tool just prints
the command they need.

**Why not default — the value of both modes:**

- **Default mode** answers: *How fast does this run on my laptop under normal
  load?* It provides an honest real-world answer. It catches production-relevant
  overheads (page faults, scheduler jitter, memory pressure) that would be
  invisible in isolation. This is what users care about day-to-day.
- **Isolated mode** answers: *How fast could this run if nothing else
  interfered?* It strips systemic noise to reveal the pipeline's inherent cost,
  enabling confident regression detection across commits. This is a debug and
  analysis tool, not a production mode.
- **Both are needed.** A change that improves isolated time but degrades default
  time is a real regression masked by noise. A change that improves default time
  and also improves isolated time is a pure win. The tool reports both
  transparently, and the comparison drives the right decision.

### 6.5 Reporting Output

Default mode appends:

> *Pass --isolated for dedicated CPU affinity.*

Isolated mode appends:

> *CPU and wall-clock converged — measurement is stable.*

---

## Key Metrics Summary (Baseline)

| Metric | 100 candles | 10,000 candles | Target | Status |
|---|---|---|---|---|
| Wall-clock | 8.32 ms (83 μs/c) | 208 ms (21 μs/c) | <5 μs/c | ⚠ Above (CPU-bound) |
| CPU/Wall | 0.98 | 0.98 | >0.8 | ✅ |
| Peak memory | 0.54 MB | 3.81 MB | — | ✅ |
| File size | 6.4 KB (65 B/c) | 20.8 KB (2.1 B/c) | 30–40 B/c | ✅ (compression) |
| GC gen-2 | 0 | 0 | <5 | ✅ |
| Bottleneck | Candle creation (22 %) | Candle creation (61 %) | — | CPU, not I/O |

The current bottleneck is `Candle` dataclass construction. For real-world usage,
API latency and rate limits will dominate — the local pipeline overhead (~20 μs
per candle) is negligible in that context.
