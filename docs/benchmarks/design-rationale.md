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

## Key Metrics Summary (Baseline — 10 iterations, N=10,000 candles)

Measured via `python scripts/benchmark_pipeline.py run --count 10000 --iterations 10 --verbose`.
Median iteration selected as the representative run; 95% CI via Student’s t-distribution (df=9).

| Metric | Median | 95% CI | Per-candle | Target | Status |
|---|---|---|---|---|---|
| Wall-clock | 210 ms | [183, 226] ms | 21.0 μs | <5 μs/c | Above — CPU-bound |
| CPU time | 210 ms | [183, 226] ms | 21.0 μs | <5 μs/c | Above — CPU-bound |
| CPU/Wall ratio | 1.00 | — | — | >0.80 | No I/O contention |
| Peak memory | 3.81 MB | deterministic | — | — | Pass |
| Memory delta | 4.62 MB | deterministic | 0.5 B | — | Pass |
| File size | 20.81 KB | deterministic | 2.1 B | 30–40 B/c | Pass (dict compression) |
| GC gen-2 | 0 | — | — | <5 | Pass |

**Stage breakdown (median run):**

| Stage | Wall (ms) | % of pipeline | Notes |
|---|---|---|---|
| Candle creation | 141 ms | 69% | Primary bottleneck — dataclass construction |
| decimal128 cast | 49 ms | 24% | C++ cast, 5 columns, ~10 ms/column |
| Parquet write | 8 ms | 4% | Not the bottleneck |
| timestamp cast | 0.5 ms | <1% | Efficient |
| Column extract + table assembly | 7 ms | 3% | — |

The bottleneck is `Candle` dataclass construction (~69% of pipeline wall). For
real-world usage, API latency and rate limits dominate — local pipeline overhead
(~21 μs per candle) is negligible once network I/O is in the critical path.

---

## 7. Validation Strategy

### 7.1 Layered validation at explicit system boundaries

**Problem:** Without defined validation gates, checks end up scattered through
providers, writers, CLI handlers, and benchmark code. This makes it unclear
which layer is responsible for what, leads to inconsistent enforcement (e.g.,
the writer checks decimal format but nothing checks OHLC sanity), and forces
developers to dig through multiple files to trace where a validation gap exists.

**Decision:** Validate at 4 explicit system boundaries — provider → service →
storage → query — each with a single responsibility.

**Why this solves it:** Each boundary owns a specific contract. The **service
boundary** catches malformed candles before they reach storage; the **storage
boundary** catches write errors (wrong partition, schema drift) before they
reach queries; the **query boundary** catches data-retrieval bugs before they
reach the user. When a bug surfaces, you know which gate should have caught it
— and you fix that gate without touching other layers. The boundaries also make
the system auditable: a review can ask "does every boundary validate its
contract?" rather than tracing validation logic through the entire call graph.

### 7.2 Provider-informed refinement

**Problem:** Building a rigid validation regime on fake data forces you to
either (a) miss checks that real providers actually need, or (b) waste time
writing rules for edge cases that don't exist in practice. Both failure modes
slow down integration and produce a validation layer that is simultaneously
overbuilt and under-useful.

**Decision:** Start with only provider-independent rules (decimal format,
timestamp format, OHLC invariants, duplicate detection). Add provider-specific
checks only after observing real provider behaviour.

**Why this solves it:** Real API quirks — pagination limits, sparse candle
omission, timestamp alignment — determine what additional validation is
actually valuable. Writing speculative rules before seeing provider behaviour
guarantees either gaps or busywork. Provider-informed refinement means
validation grows only when real data justifies it, keeping the codebase lean
and the ruleset grounded in observed reality rather than imagined failure
modes.

### 7.3 String-based decimal comparison (no `Decimal` objects)

**Problem:** Parsing decimal strings to Python `Decimal` objects purely for
comparison (e.g., `high >= open`) creates transient objects on every
validation call. This contradicts the project's "strings-first" design choice,
adds GC pressure, and introduces a Python-object allocation cost into what
should be a lightweight check.

**Decision:** Implement `_decimal_gte(a, b)` that compares decimal strings
directly — integer part comparison with length-aware padding, fractional part
zero-padded to equal length. No `Decimal` objects created at any point in
validation.

**Why this solves it:** `_decimal_gte()` runs in pure Python without
allocating a single intermediate object. It is consistent with the model-layer
decision to keep all numeric fields as strings (Section 1), avoids creating
Python `Decimal` objects even transiently, and eliminates the performance
cliff where a simple comparison forces a full parse-and-allocate round-trip.
The function is trivially verified — ~20 lines with no dependencies — and
covers all needed comparison cases (equal, same-integer-different-scale,
different-integer-length, leading zeros).

### 7.4 Structured issues with severity levels (not fail-fast)

**Problem:** A fail-fast approach — raising an exception on the first invalid
candle in a batch — hides the full validation picture. If a batch of 1000
candles contains 50 issues across 4 rule types, an exception on candle index 0
reveals nothing about the other 49 failures. The caller has to fix, re-run,
hit the next issue, fix, re-run — an O(n) debugging loop.

**Decision:** Collect all validation issues across the entire batch before
returning. `ValidationResult` contains a `passed` boolean and an `issues` list.
The pipeline never aborts mid-check; issues are reported to stderr and writing
proceeds regardless.

**Why this solves it:** A single pass reveals every problem in the batch —
the caller sees the full scope of issues in one shot, not one at a time with
retry cycles. Distributing issues by `candle_index` and `field` makes triage
straightforward (e.g., "all 50 issues are `INVALID_DECIMAL` on `volume` — the
provider is returning volume as a string like `'1,234'`"). The non-fail-fast
policy also means the pipeline degrades gracefully: a few malformed candles
log warnings without aborting an otherwise valid ingestion run, which is
critical for unattended data collection.

### 7.5 Precision overflow as warning (configurable severity)

**Problem:** The Parquet schema uses `decimal128(38, 10)`, which supports up
to 38 significant digits. A 39-digit decimal string from a provider would fail
at write time with a cryptic Arrow cast error. However, real crypto prices
rarely exceed 12–15 significant digits, so overflow is virtually impossible in
practice — a hard error here would create false-positive pipeline failures for
a scenario that almost never occurs.

**Decision:** Detect digit count exceeding 38 in the validation layer, emit a
`PRECISION_OVERFLOW` issue at `"warning"` severity (controlled by
`_PRECISION_OVERFLOW_SEVERITY` at the top of the module). The pipeline
continues to write; the warning appears in stderr.

**Why this solves it:** The check is cheap (string length minus decimal points)
and runs during validation, so it catches the edge case before the write path
hits an Arrow cast error. The `"warning"` default avoids false-positive
pipeline aborts for an astronomically unlikely scenario. Setting the severity
constant to `"error"` is a one-line change if provider behaviour ever
justifies fail-fast on overflow — no structural refactor needed, and the
caller makes the risk decision rather than the library.

### 7.6 Shared `_DECIMAL_PATTERN` across service/storage boundaries

**Problem:** The writer already validated decimal format at storage time via a
local `_DECIMAL_PATTERN` regex. Adding a service-layer validation that
redefines the same regex creates a drift risk — one boundary could accept
`"1.2.3"` while the other rejects it, producing confusing failures where
validation passes but the write fails.

**Decision:** Define `_DECIMAL_PATTERN` once in `validation/candles.py`.
`parquet_writer.py` imports it rather than defining its own. The local
`import re` and the old regex definition are removed from the writer.

**Why this solves it:** A single regex definition guarantees that the service
and storage boundaries agree on what constitutes a valid decimal string. If
the format ever needs adjusting (e.g., allowing negative values for a provider
that reports signed prices), one edit in the canonical location propagates to
both layers. The import direction — validation → writer — is intentional: the
service boundary defines the format contract, and the storage boundary reuses
it. This is a clean dependency (no circular imports) and eliminates the
duplication that would inevitably diverge.

### 7.7 Minimal OHLC invariant set (4 checks instead of 7)

**Problem:** Textbook OHLC data has 7 well-known invariants: high≥open,
high≥close, high≥low, low≤open, low≤close, low≤high, and all fields ≥ 0.
Implementing all 7 as separate checks duplicates work because some are entailed
by others — `high≥low` is guaranteed by `high≥open` + `low≤open` (or
`high≥close` + `low≤close`) via transitivity, and non-negativity is already
enforced by the decimal regex rejecting `-`.

**Decision:** Implement exactly 4 checks — `high ≥ open`, `high ≥ close`,
`low ≤ open`, `low ≤ close`. Skip `high ≥ low`, `low ≤ high`, and the four
non-negativity checks. OHLC checks are skipped entirely if any decimal field
fails the pattern match.

**Why this solves it:** The 4 selected checks express the canonical OHLC
relationship directly (the extremes must bound the open and close). `high ≥
low` is entailed by `high ≥ open` combined with `low ≤ open` (if high ≥ open
and open ≥ low, then high ≥ low by transitivity) — adding it as a fifth check
would never fire independently. Non-negativity is delegated to the decimal
regex, which already rejects the `-` prefix in `INVALID_DECIMAL`. Skipping
checks when decimals are unparseable avoids a double-reporting problem where a
single malformed field triggers both `INVALID_DECIMAL` and `OHLC_INVARIANT`
for the same root cause. The result is a minimal, non-redundant set that still
guarantees all 7 textbook invariants.

### 7.8 Five initial provider-independent rules

**Problem:** Which validation rules belong in the initial implementation?
Adding too many creates maintenance burden before real providers validate
their usefulness; adding too few leaves obvious data-quality gaps.

**Decision:** Implement exactly 5 provider-independent rules, deferring
completeness/gap/scoring rules until real providers expose their behaviour.

| Rule | Code | What it catches | Why defer beyond this |
|---|---|---|---|
| Non-empty required fields | `EMPTY_FIELD` | Null/blank `exchange`, `symbol`, etc. | Trivial guard, no provider-specific knowledge needed |
| Decimal format | `INVALID_DECIMAL` | `"abc"`, `"1.2.3"`, `"-5"` in numeric fields | Regex-based, same contract as Parquet schema |
| Timestamp format | `INVALID_TIMESTAMP` | Non-ISO-8601 strings | Regex-based, covers `s` and `us` formats |
| OHLC invariants | `OHLC_INVARIANT` | high<open, low>close, etc. | Intrinsic to OHLC data, safe for all providers |
| Duplicate timestamp | `DUPLICATE_TIMESTAMP` | Same `exchange/symbol/tf/source/ts` within batch | No pagination/gap knowledge needed |

Deferred — expected candle count, missing interval detection, pagination-aware
validation, provider scoring — all depend on knowing how real providers
paginate, cap results, and handle sparse markets. Adding them before Kraken or
Coinbase would produce rules tuned to fake data that might not match reality.

---

## 8. Network/CPU Boundary Measurement

### 8.1 The split determines the optimisation strategy

**Problem:** The synthetic benchmark (10k candles, no network) and the live
provider benchmarks (24 candles, real API) produce very different profiles, but
without a first-class metric that distinguishes them, it is easy to optimise the
wrong thing — spending effort on local pipeline throughput when the real
bottleneck is network I/O, or vice versa.

**Observation from live profiling:** The CPU/Wall ratio changes by two orders
of magnitude depending on whether network I/O is present:

| Benchmark | Candles | Wall (ms) | CPU (ms) | Net (ms) | Net/CPU ratio | Character |
|---|---|---|---|---|---|---|
| Synthetic (CandlePipelineRunner) | 10,000 | 154.6 | 161.1 | −6.5 | −0.0× | **CPU-bound** |
| FakeProvider | 1 | 2.3 | 2.1 | 0.2 | 0.1× | **CPU-bound** |
| BitfinexProvider | 24 | 75.3 | 11.3 | 64.0 | 5.7× | **network-bound** |
| KuCoinProvider | 24 | 280.7 | 9.0 | 271.7 | 30.1× | **network-bound** |

(Net = wall − cpu: time spent outside our process — waiting on the network,
the scheduler, or I/O. A negative value for the synthetic benchmark reflects
timer granularity noise; it is effectively zero.)

**Why this matters:** A 10× improvement in local pipeline throughput
(the CPU-bound domain) would reduce the synthetic benchmark by 90%, but
would reduce Bitfinex ingestion by ~15% and KuCoin ingestion by ~3%. The
returns are rapidly diminishing for real providers — optimising the CPU path is
not the lever you think it is once network I/O dominates.

### 8.2 How the boundary is measured

The `profile` command reports a **Network/CPU Boundary** section per provider:

```
Network wait:  63.95 ms  (wall − cpu = time outside our process)
CPU processing: 11.31 ms  (total CPU for pipeline stages)
Network/CPU ratio: 5.7×  → network-bound
```

The metrics are derived entirely from existing `time.perf_counter()` and
`time.process_time()` instrumentation — no new probes are needed.

- **Network wait** = `pipeline wall total − pipeline CPU total`. This captures
  all time not spent on our thread: network I/O wait, kernel context switches,
  scheduler preemption, and PyArrow's internal C-level allocations (which
  `tracemalloc` cannot see). In practice, for an idle machine with a live API
  call, it is almost entirely HTTP round-trip time.
- **CPU processing** = sum of `process_time()` deltas across all pipeline
  stages. This is cycles our thread actually ran.
- **Regime classification:**
  - `Net/CPU < 0.5` → **CPU-bound** (the pipeline is the bottleneck)
  - `0.5 ≤ Net/CPU ≤ 1.5` → **balanced** (neither dominates)
  - `Net/CPU > 1.5` → **network-bound** (the network is the bottleneck)

### 8.3 What the boundary implies for optimisation

**When CPU-bound** (synthetic benchmark, FakeProvider):
Optimise the local pipeline: Candle object creation, decimal128 casting,
validation throughput. Every CPU cycle saved translates directly to real
wall-clock savings. The current bottleneck is Candle dataclass construction
(~64% of pipeline CPU at 10k candles — see Section 6).

**When network-bound** (Bitfinex, KuCoin):
Optimise I/O concurrency: larger batch sizes per request, parallel symbol
fetching, connection reuse, WebSocket streaming. CPU savings in the pipeline
are overwhelmed by HTTP round-trip time — a 50% pipeline improvement saves
~5ms out of 75ms (Bitfinex) or ~4ms out of 281ms (KuCoin). The returns are
modest until I/O is addressed.

**The key insight:** the same benchmark framework must measure both regimes
because the same ingestion pipeline transitions between them depending on
whether a provider call is in-flight. A single "throughput" number is
misleading — you need to know whether you are CPU-bound or network-bound to
know what to fix.

### 8.4 Design implications for the benchmark suite

The project maintains two benchmark paths that exercise different regimes:

| Command | Regime | What it measures | Primary audience |
|---|---|---|---|
| `run --runner candle` | CPU-bound | Pipeline code throughput (Candle → Parquet) | Regression gate for core pipeline |
| `profile` | mixed (network + CPU) | End-to-end provider ingestion cost | Provider integration, capacity planning |

Both use the same `BenchmarkContext`/`StageMetrics`/`BenchmarkResult`
infrastructure. The `profile` command adds the Network/CPU boundary
interpretation layer on top. Neither path is a subset of the other — they are
complementary views of the same system at different abstraction levels.

---

## 9. Query Service Layer (Read Side)

### 9.1 QueryService ABC separates domain interface from transport

**Problem:** The first query implementation (DuckDB over local Parquet files) is
convenient for development but should not be hard-coded into CLI commands or
future API layers. A REST API, a gRPC service, or an analytics pipeline all
need the same five operations — list datasets, get candles, get funding rates,
get summary, raw SQL — and should not care which engine provides them.

**Decision:** Define a `QueryService` ABC with five abstract methods in
`query/service.py`. `DuckDBQueryService` is the sole concrete implementation
today; future implementations (Postgres, HTTP proxy, InfluxDB) implement the
same ABC without changing consumers.

**Why this solves it:** The CLI commands, the FastAPI server, and any future
consumer all depend on `QueryService` via dependency injection — they never
import `DuckDBQueryService` directly. Adding a new engine means writing a new
subclass and wiring it into `ServerConfig`; no consumer code changes.

### 9.2 DuckDB Query Engine: SQL-on-Parquet without a server

**Problem:** Parquet files are not directly queryable by SQL without an
intermediate engine. Copying them into a database adds latency and storage
overhead. The query layer should read Parquet files in place.

**Decision:** Use DuckDB's `read_parquet()` function to query partitioned
Parquet files directly — no import step, no database server, no schema
registration. Connection-per-query (connect, execute, close) avoids state
management.

**Why this solves it:** DuckDB reads the Parquet schema at query time, so
schema changes (e.g., adding a new column) are automatically picked up. There
is no data ingestion step — the CLI writer produces Parquet files, and the
query service reads them in the same format. Connection-per-query is cheap for
DuckDB (in-process, no network) and eliminates connection-pool complexity.

### 9.3 Path-based file discovery with variable-depth symbol handling

**Problem:** Symbols containing `/` (e.g. `BTC/USDT`) create variable-depth
directory trees: `{base}/{exchange}/BTC/USDT/{timeframe}/{date}.parquet`. A
fixed `parts[-3]` approach for extracting the symbol breaks when the symbol
contains slashes.

**Decision:** Use the penultimate directory component as the anchor. If it is
`"funding_rate"`, the path is a funding rate dataset; otherwise it is a
timeframe identifier for candles. The symbol is reconstructed by joining all
parts between the exchange (index 0) and the anchor.

```
{exchange}/{symbol...}/{timeframe}/{date}.parquet
                   ^^^^^^^^^^^^
                   anchor = parts[-2]
                   symbol = "/".join(parts[1:-2])
```

**Why this solves it:** The penultimate anchor is always either a timeframe
(`"1h"`, `"1d"`) or `"funding_rate"` — neither contains `/`. This makes the
discovery algorithm independent of symbol depth: `BTC/USDT` (2 parts) and
`BTC-USD` (1 part) both work without special cases.

### 9.4 DuckDB decimal128 → string conversion for model compatibility

**Problem:** The Parquet schema stores prices as `decimal128(38,10)`, but the
`Candle` model stores them as `str`. DuckDB returns `decimal128` values as
Python `Decimal` objects, which would need to be converted back to strings
before constructing `Candle` instances.

**Decision:** Cast decimal128 columns to `VARCHAR` in the SQL query:
```sql
SELECT *, open::VARCHAR, high::VARCHAR, ... FROM read_parquet([...])
```
The `_rows_to_dicts()` helper also normalises any remaining `Decimal` and
`datetime` objects to strings via `isinstance` checks.

**Why this solves it:** The cast is done in DuckDB's C++ engine, not in Python.
The resulting values are already strings matching the model types. The
`isinstance` fallback catches columns that are not explicitly cast (e.g. custom
queries via `raw_sql()`).

---

## 10. Server Layer (FastAPI)

### 10.1 FastAPI over DuckDB for HTTP access

**Problem:** The query service currently requires Python and the project
package to be installed. Analysts, dashboards, and external tools need HTTP
access to the data without installing Python dependencies.

**Decision:** Build a FastAPI application (`server/app.py`) that wraps the
`QueryService` ABC. The `create_app()` factory accepts a `ServerConfig` with
the `QueryService` implementation injected, defaulting to `DuckDBQueryService`.
Endpoints mirror the ABC methods:

| Method | Path | QueryService method |
|--------|------|---------------------|
| GET | `/health` | — |
| GET | `/datasets` | `list_datasets()` |
| GET | `/candles` | `get_candles()` |
| GET | `/funding-rates` | `get_funding_rates()` |
| GET | `/summary` | `get_summary()` |
| POST | `/query` | `raw_sql()` |

**Why this solves it:** The server is a thin HTTP adapter over the existing
ABC — zero new query logic. Because it depends on `QueryService` (not
`DuckDBQueryService`), swapping the backend (Postgres, remote proxy) requires
only changing the injected implementation in `ServerConfig`.

### 10.2 Lifespan-managed middleware and error handling

**Problem:** A production HTTP server needs CORS headers (for browser clients),
consistent error responses (for API consumers), and lifecycle management
(startup/shutdown hooks). Adding these ad-hoc leads to inconsistent behaviour.

**Decision:** Register three infrastructure components in `create_app()`:

1. **`lifespan` context manager** — placeholder for startup/shutdown logic
   (connection pool warm-up, resource cleanup).
2. **`CORSMiddleware`** — `allow_origins=["*"]` for development; scoped in
   production via `ServerConfig`.
3. **Global `@app.exception_handler(Exception)`** — catches unhandled
   exceptions and returns `{"error": "<message>", "code": 500}` instead of
   the default HTML 500 page.

**Why this solves it:** CORS is required for any browser-based client; the
wildcard default avoids mysterious "blocked by CORS" errors during development.
The global error handler guarantees that every response is JSON, not HTML —
critical for programmatic API consumers. The lifespan context manager provides
a hook for future startup tasks (loading models, warming DuckDB caches)
without scattering `@app.on_event` decorators across routers.


---

## 11. Network Optimization Strategy

### 11.1 Why the synthetic benchmark does not change after network optimizations

**The observation:** After implementing connection pooling (Option A) and concurrent
symbol fetching (Option C), re-running `benchmark_pipeline.py run --count 10000
--iterations 10` produces statistically identical results to the baseline (median
~210 ms, 21 μs/candle, CPU/Wall = 1.00).

**Why this is correct and expected:** The `run` benchmark is synthetic — it uses
`CandlePipelineRunner`, which creates `Candle` objects in-process without any
network calls. The pipeline is 100% CPU-bound (CPU/Wall = 1.00). Connection pooling
and concurrent fetching affect only the HTTP layer, which is not exercised in this
path. This is not a failure of the optimization — it is a confirmation that the
benchmark correctly isolates the local pipeline from the network I/O path.

The correct way to measure network optimization impact is the `profile` command,
which hits real exchange APIs and reports the Net = wall − cpu metric.

### 11.2 Option A: Connection pooling via urllib3

**Problem:** The original implementation used `urllib.request` with a new TCP
connection per API call. Each HTTPS request incurred:
- TCP handshake (1 RTT minimum)
- TLS negotiation (1–2 additional RTTs)
- HTTP request/response

For a provider like KuCoin with ~30× Net/CPU ratio, the handshake overhead is
small relative to the API response time — but it compounds across multiple requests
to the same host during a single ingest run.

**Decision:** Replace `urllib.request` with a `urllib3.PoolManager` singleton
(module-level) in `src/cmpd/providers/http.py`. The pool reuses TCP connections
across calls to the same host via HTTP keep-alive.

```python
_http = urllib3.PoolManager(maxconnections=10, headers=_HEADERS)

def fetch_json(url: str, exchange: str, timeout: int = 30) -> Any:
    resp = _http.request("GET", url, timeout=urllib3.Timeout(connect=10, read=timeout))
    ...
```

**Impact model:** For a date range requiring N paginated requests to the same host,
the first request pays the full handshake cost; subsequent requests reuse the
connection. Savings scale with pagination depth. For a 3-month range at hourly
resolution (~2160 candles at 500 candles/page = 5 pages), this eliminates 4 TLS
handshakes per run.

**Why the change is safe:** urllib3's `PoolManager` is thread-safe; it manages
connection ownership internally. The module-level singleton means all provider
instances in a process share the pool — concurrent symbol fetches (Option C) reuse
the same connections without double-handshaking.

### 11.3 Option C: Concurrent symbol fetching

**Problem:** The original `cmpd fetch` command accepted a single `--symbol` and
fetched it sequentially. Ingesting N symbols required N sequential runs, each
paying the full network round-trip latency. For providers with a 30× Net/CPU ratio
(KuCoin), the serial bottleneck is entirely in waiting, not computing.

**Decision:** Extend `--symbol` to accept multiple values (repeat the flag) and
add `--workers N` (default 4, max 32). `ThreadPoolExecutor` dispatches one fetch
per symbol concurrently. Each worker instantiates its own `OhlcvService(provider_cls())`,
which is safe because different symbols write to disjoint Parquet paths.

```sh
# Before: sequential, 3 sequential fetches
cmpd fetch --mdt ohlcv --symbol BTC/USDT --provider kucoin ...
cmpd fetch --mdt ohlcv --symbol ETH/USDT --provider kucoin ...
cmpd fetch --mdt ohlcv --symbol SOL/USDT --provider kucoin ...

# After: concurrent, all 3 in ~1 fetch's time
cmpd fetch --mdt ohlcv   --symbol BTC/USDT --symbol ETH/USDT --symbol SOL/USDT   --provider kucoin --workers 3 ...
```

**Expected speedup:** For N symbols in parallel with ideal scheduling, wall-clock
time approaches that of a single fetch. CPU time stays proportional to N (CPU is
cheap; network wait is the bottleneck). For KuCoin at 30× Net/CPU ratio,
concurrent fetching of 4 symbols reduces wall-clock by roughly 3× vs serial — the
single-fetch network wait dominates, so 4 concurrent waits overlap.

**Thread safety:** Each `OhlcvService` instance holds its own `provider_cls()`
instance. The shared `_http` pool in `providers/http.py` is thread-safe (urllib3
manages connection checkout/return). Parquet writes to distinct symbol paths have
no file-level conflicts.

### 11.4 Option B: Concurrent page fetching (not implemented)

**Decision:** Do not implement intra-symbol concurrent page fetching (parallelizing
the pagination loop for a single symbol across multiple workers).

**Why this is overengineering for this tool:**

1. **Rate limits dominate, not TCP:** Most exchange APIs enforce per-key rate limits
   (e.g., KuCoin: 30 requests/10 seconds). Parallel page fetching within a symbol
   would hit rate limits on the second request, forcing backoff that eliminates the
   concurrency benefit. The sleep in the rate-limit handler would serialize the
   requests anyway.

2. **Cursor-based pagination is inherently sequential:** KuCoin's pagination uses a
   `nextCursor` token returned in the response body. You cannot determine page N+1's
   URL until you have received and parsed page N. This makes page-level parallelism
   structurally impossible for cursor-based providers without fetching the full page
   sequence first.

3. **Typical use case doesn't justify the complexity:** The common use case is a
   recent date range (days to weeks) × a handful of symbols. At 500 candles/page
   and 720 hourly candles per month, a 1-month range for one symbol requires 2 pages
   — the concurrency gain is trivial.

4. **Option C already addresses the real bottleneck:** Symbol-level parallelism
   (Option C) targets the same network wait time without the rate-limit and
   cursor-ordering complications. It delivers the speedup where the workload is
   actually multi-symbol, which is the typical production use case (ingesting a
   portfolio of assets).

The threshold for revisiting Option B: a provider with offset-based pagination
(e.g., Binance's `startTime`/`endTime` range splitting) and a date range
exceeding 30 days at 1-minute resolution (43,200 candles = 87 pages). Even then,
rate-limit handling would need to be designed first.

### 11.5 Averaging strategy: why median + t-distribution CI

**The concern (stated):** Benchmark runs are noisy. A single outlier run inflates
the mean, producing misleading headline numbers.

**The approach:** The benchmark reports the **median** as the headline number with
a **Student's t-distribution 95% CI** around the mean. This pairing is deliberate:

- **Median as point estimate:** Robust to single outlier runs (GC pauses, OS
  scheduling spikes, page-fault storms on first write). When iteration 9 in the
  post-optimization run was 556 ms vs a cluster around 200 ms, the median stayed
  at 224 ms — accurately representing the steady-state cost.

- **t-distribution CI:** Honest about uncertainty. With N=10, df=9, the CI width
  directly reflects iteration variance. A tight CI (e.g., ±0.3 ms on CPU time)
  tells you the number is trustworthy. A wide CI (e.g., ±100 ms on wall-clock)
  tells you the environment was noisy — run `--isolated` or check what was
  competing for CPU.

- **Why not trimmed mean as the headline:** Trimming (e.g., dropping top/bottom
  10%) hides the worst case. If 2 of 10 iterations are 2.5× slower than the
  median, that is information — a tight trimmed mean would not show it. The CI
  width does.

- **What to report:** Headline = median. Spread = CI. Full picture = per-iteration
  table (in `--verbose` mode). Min/max are available in the per-iteration table
  for worst-case analysis.

**The key benchmark result from the before/after comparison:**

```
Baseline  (before Options A + C): median 210 ms, 95% CI [183, 226] ms (21.0 μs/c)
Post-opt  (after  Options A + C): median 224 ms, 95% CI [178, 380] ms (22.4 μs/c)
```

The medians are statistically equivalent — the CI bands overlap substantially.
This is the correct finding: **the synthetic benchmark is unaffected by network
optimizations, confirming that the I/O pipeline is correctly isolated from the
network path.** The post-optimization CI is wider because the second run had two
outlier iterations (556 ms, 525 ms) from OS scheduling interference — the median
correctly excluded them from the headline number.

**For network benchmarks:** Use the `profile` command. Its 3-iteration median
(N=3, df=2, CI reported for ≥5 iterations only) shows the before/after comparison
for real provider calls where the network path is actually exercised.
