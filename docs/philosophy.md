# Philosophy

This project treats market data infrastructure as a systems engineering
problem. The following principles govern every architectural decision.

## Dual-mode deployment: local and cloud

The pipeline runs identically against local disk and cloud blob storage. No code changes are needed to switch between them — only the storage root differs.

**Local mode:** Data lives in Parquet files on local disk. DuckDB queries them in place via `read_parquet`. The whole pipeline — fetch, validate, store, query — runs on a single machine with no external dependencies. This is the default, deliberately minimal deployment for development, benchmarking, and small-scale use.

**Cloud mode:** The same pipeline runs against Azure Blob Storage by changing the `--output` and `--path` flags to an `az://container/prefix` URI. The `DuckDBQueryService` loads the `azure` DuckDB extension for reads; the writer uses `adlfs` and Azure Blob leases to make concurrent writes safe. No new infrastructure is required.

This is a deliberate inversion of the typical "write to a database, then read from it" pattern. Parquet files are the interchange format: portable, version-controllable, and readable by any Parquet-compatible tool without an import step.

Local and cloud deployments share an identical code path — only the storage root differs. The SDK and CLI abstract this choice, letting consumers target either environment with a single parameter change.

## Strings-first

All numeric fields in `Candle` and `FundingRate` models are stored as
`str`, not `Decimal` or `float`. Type coercion is deferred to the write path,
where PyArrow's C++ `.cast()` converts strings to `decimal128(38,10)` in a
single vectorised call.

This saves ~68 % per-candle memory vs `Decimal`-based models and eliminates
transient Python `Decimal` objects from the hot path. Validation operates on
the string directly via regex — no parse-and-allocate round-trip.

## Measured performance

Decisions are backed by benchmark evidence, not intuition. The pipeline has
two measurement modes:

- **Default** — runs on a shared core with normal scheduler priority,
  reflecting real-world performance under everyday load
- **`--isolated`** — pins the process to a dedicated core via
  `sched_setaffinity` and raises priority via `nice(-10)`, revealing the
  pipeline's inherent cost without OS noise

A change that improves isolated time but degrades default time is a real
regression masked by noise. Both numbers are reported transparently.

## Provider-informed validation

Validation rules are added only after observing real provider behaviour.
Starting with only provider-independent rules (decimal format, timestamp
format, OHLC invariants, duplicate detection) avoids the two classic failure
modes: missing checks that real providers need, and wasted effort on edge
cases that don't exist in practice.

Real API quirks — pagination limits, sparse candle omission, timestamp
alignment — determine what additional validation is valuable. Rules grow from
observed reality, not speculation.

## Dependency inversion at every boundary

Every layer depends on an ABC, not a concrete implementation:

| Boundary | ABC | Implementation |
|----------|-----|----------------|
| Provider | `OHLCVProvider` | `FakeProvider`, `BitfinexProvider`, `KuCoinProvider`, … |
| Query | `QueryService` | `DuckDBQueryService` |
| Server | `QueryService` (injected) | FastAPI wraps the ABC |

Adding a new provider or query engine means writing a new subclass — consumer
code (CLI, API, benchmarks) never changes.
