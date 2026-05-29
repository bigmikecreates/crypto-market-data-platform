# Storage: End-to-End Write Path

## Pipeline Overview

```
cmpd fetch --provider bitfinex --symbol BTC/USD --timeframe 1h --start 2024-01-01 --end 2024-01-03

    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Stage 1 — Provider                                  │
│ Raw API response → list[Candle] with all-string     │
│ fields                                              │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Stage 2 — Validation (advisory)                     │
│ Per-candle checks on string values; issues printed  │
│ to stderr, writes proceed regardless                │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Stage 3 — Partition routing                         │
│ Group candles by date → {exchange}/{symbol}/        │
│ {timeframe}/{YYYY-MM-DD}.parquet                    │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Stage 4 — Type casting                              │
│ String columns → decimal128(38,10) for OHLCV/volume │
│ String timestamps → timestamp[s]                    │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Stage 5 — Row-level upsert merge                    │
│ For existing partitions: merge by key; skip         │
│ identical rows, replace changed rows, append new    │
│ rows.                                               │
└─────────────────────────────────────────────────────┘
    │
    ▼
    {date}.parquet (SNAPPY, partitioned by date)
```

---

## Stage 1 — Provider

Each provider adapter (`providers/bitfinex.py`, `providers/kucoin.py`, etc.)
implements the `OHLCVProvider` interface. The provider converts the canonical
symbol/timeframe to the exchange's native naming, constructs the API URL,
loops paginated responses, and maps each raw JSON row to a `Candle` dataclass
with all-string fields.

All numeric fields are strings at this point. This keeps the provider boundary
simple — no type casting, no Decimal imports, no schema decisions.

→ See `OHLCVProvider` in the [Python API Reference](reference/python-api.md)
for the exact method signature.

---

## Stage 2 — Validation

`validate_candle_batch()` runs per-candle checks on the string values.
Validation is **advisory** — issues are printed to stderr but writes proceed.
The persisted data can be inspected later to diagnose provider issues.

→ See [Validation Rules Reference](reference/validation-rules.md) for the
exact rule codes and descriptions.

---

## Stage 3 — Partition Routing

Each candle is routed to a file based on its date.

```
data/{exchange}/{symbol}/{timeframe}/{date}.parquet
```

Candles are grouped by target path so each partition is processed independently.

→ See [Parquet Schema Reference](reference/parquet-schema.md) for the
exact partition layout and path helpers.

---

## Stage 4 — Type Casting

`candle_to_table()` converts a group of same-partition candles into a single
PyArrow table by casting string fields to their Parquet types. String columns
(`exchange`, `symbol`, `timeframe`, `source`) remain as strings. Numeric
columns are cast via PyArrow's C++ `.cast()` to `decimal128(38,10)`. Timestamp
columns are cast to `timestamp[s]` (or `timestamp[us]` depending on config).

### Why `decimal128(38, 10)`?

`decimal128(38,10)` is the only type that provides exact decimal arithmetic,
native DuckDB sort/filter, and a fixed schema independent of ticker price
ranges. UTF8 would save the write-time `.cast()` kernel but push that cost
to every read query, break sort order, and lose predicate pushdown.

### Why strings until storage?

1. **Provider boundary stays simple** — most APIs return prices as JSON strings;
   providers just pass them through without import or type-conversion overhead
2. **Single schema authority** — the storage boundary owns the Parquet type
   decision. Changing column types requires changing one function, not six
   providers.

→ See `candle_to_table()` in the [Python API Reference](reference/python-api.md)
for the exact function signature, and [Parquet Schema Reference](reference/parquet-schema.md)
for the full column-type mapping.

---

## Stage 5 — Row-Level Upsert Merge

This is the most important recent addition. When a partition file already exists,
the old behaviour was blind `concat_tables` — which could produce duplicate rows
if the same time range was fetched twice.

### Merge key

The row identity key for candles:

```
(exchange, symbol, timeframe, source, timestamp)
```

For funding rates:

```
(exchange, symbol, source, timestamp)
```

This matches the duplicate-detection key used in validation.

### Algorithm

For each partition file that exists: read existing rows, merge incoming rows
by key (skip identical, replace changed, append new), write back.

### Merge strategies

Two implementations, selected automatically or by user override:

- **`memory` (set-based)** — Python `set` of row keys, linear scan. Used for
  partitions with fewer than 50,000 rows.
- **`duckdb` (SQL anti-join)** — `LEFT JOIN ... WHERE NULL` + `UNION ALL` via
  DuckDB. Used for partitions with 50,000+ rows.

### Properties

- **Idempotent**: fetching the same range twice produces identical files.
- **Self-healing**: a corrected candle from the provider replaces the stale
  version on the next fetch.
- **Append-safe**: new rows are added without affecting existing rows.

→ See merge function signatures and strategy details in the
[Python API Reference](reference/python-api.md).

---

## Funding Rate Variant

Funding rates follow the same stages with a different column set and path.
The merge key omits `timeframe` (funding rates have no timeframe field).

→ See [Parquet Schema Reference](reference/parquet-schema.md) for the
exact column set and partition layout for funding rates.
