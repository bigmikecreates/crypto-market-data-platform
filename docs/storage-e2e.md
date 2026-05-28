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
implements the `OHLCVProvider` interface:

```python
class OHLCVProvider(ABC):
    def fetch_ohlcv(
        self, symbol: str, timeframe: str,
        start: datetime, end: datetime,
    ) -> list[Candle]: ...
```

The provider:

1. Converts canonical symbol/timeframe to the exchange's native naming
2. Constructs the API URL with `start`/`end` parameters
3. Loops paginated responses (if needed)
4. Maps each raw JSON row to a `Candle` dataclass with all-string fields

A candle arrives as:

```python
Candle(
    exchange="bitfinex",
    symbol="BTC/USD",
    timeframe="1h",
    timestamp="2024-01-01T00:00:00",
    open="42331",
    high="42591",
    low="42331",
    close="42522",
    volume="9.03426154",
    source="bitfinex",
)
```

All numeric fields are strings at this point. This keeps the provider boundary
simple — no type casting, no Decimal imports, no schema decisions.

---

## Stage 2 — Validation

`validate_candle_batch()` (`validation/candles.py`) runs per-candle checks on
the string values:

| Check | Rule |
|---|---|
| `EMPTY_FIELD` | No field is blank |
| `INVALID_DECIMAL` | OHLCV values match signed decimal regex |
| `NEGATIVE_VALUE` | No negative prices/volume |
| `PRECISION_OVERFLOW` | >38 digits (warning) |
| `INVALID_TIMESTAMP` | ISO-8601 format |
| `OHLC_INVARIANT` | `high ≥ open/close ≥ low` |
| `DUPLICATE_TIMESTAMP` | No duplicate key within batch |

Validation is **advisory** — issues are printed to stderr but writes proceed.
The persisted data can be inspected later to diagnose provider issues.

---

## Stage 3 — Partition Routing

Each candle is routed to a file based on its date:

```python
def _path_for_candle(c: Candle, base_path: str) -> Path:
    date_str = c.timestamp[:10]
    return Path(base_path) / c.exchange / c.symbol / c.timeframe / f"{date_str}.parquet"
```

Resulting layout:

```
data/
└── bitfinex/
    └── BTC/
        └── USD/
            └── 1h/
                ├── 2024-01-01.parquet   (24 rows)
                └── 2024-01-02.parquet   (24 rows)
```

Candles are grouped by target path via `defaultdict(list)` so each partition is
processed independently.

---

## Stage 4 — Type Casting

`candle_to_table()` (`storage/parquet_writer.py:44`) converts a group of same-partition
candles into a single PyArrow table:

```python
{
    "exchange":  string,
    "symbol":    string,
    "timeframe": string,
    "timestamp": cast(string → timestamp[s]),
    "open":      cast(string → decimal128(38, 10)),
    "high":      cast(string → decimal128(38, 10)),
    "low":       cast(string → decimal128(38, 10)),
    "close":     cast(string → decimal128(38, 10)),
    "volume":    cast(string → decimal128(38, 10)),
    "source":    string,
}
```

### Why `decimal128(38, 10)`?

| Type | Exact? | Sortable? | Query cost | Storage |
|---|---|---|---|---|
| `decimal128(38,10)` | Yes | Yes | Native | 16 bytes/val |
| `float64` | No — rounding errors | Approx | Native | 8 bytes/val |
| `utf8` | Yes | No — text sort | CAST per query | Variable |
| `int64 * scale` | Yes | Yes | Native but manual | 8 bytes/val |

`decimal128(38,10)` is the only type that provides exact decimal arithmetic,
native DuckDB sort/filter, and a fixed schema independent of ticker price ranges.
UTF8 would save the write-time `.cast()` kernel but push that cost to every
read query, break sort order, and lose predicate pushdown.

The cast is a C++ PyArrow kernel operating on arrays, not per-row Python —
the cost is negligible for any realistic partition size.

### Why strings until storage?

The `Candle` model uses strings for two reasons:

1. **Provider boundary stays simple** — most APIs return prices as JSON strings;
   providers just pass them through without import or type-conversion overhead
2. **Single schema authority** — the storage boundary owns the Parquet type
   decision. Changing column types (e.g. `decimal128(38,8)`) requires changing
   one function, not six providers

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

For each partition file that exists:

```
existing = read_parquet(path)

for each incoming_row:
    if key in existing:
        if data differs → replace (keep incoming, drop existing)
        if data identical → skip
    else:
        append (new row)

result = (unchanged existing rows) + (updated rows) + (new rows)
write result back to path
```

### Merge strategies

Two implementations, selected automatically or by user override:

| Strategy | How it works | Used when | Memory |
|---|---|---|---|
| `memory` (set-based) | Python `set` of row keys, linear scan | `< 50K` rows/partition | ~7.5 MB at 50K rows |
| `duckdb` (SQL anti-join) | `LEFT JOIN ... WHERE NULL` + `UNION ALL` via DuckDB | `≥ 50K` rows/partition | Minimal (C++ memory) |

The threshold `_ROW_MERGE_THRESHOLD = 50_000` was chosen so the Python key set
never exceeds ~10 MB. At typical granularities:

| Timeframe | Rows/day | Key set memory | Strategy |
|---|---|---|---|
| 1h | 24 | ~4 KB | `memory` |
| 5m | 288 | ~43 KB | `memory` |
| 1m | 1,440 | ~216 KB | `memory` |
| 1s | 86,400 | ~13 MB | `duckdb` |

User can override with `--merge-strategy`:

```bash
cmpd fetch --merge-strategy duckdb  # force DuckDB path
cmpd fetch --merge-strategy memory  # force set-based path
```

### Properties

- **Idempotent**: fetching the same range twice produces identical files (no row
  bloat)
- **Self-healing**: a corrected candle from the provider replaces the stale
  version on the next fetch
- **Append-safe**: new rows (timestamps not yet in the file) are added without
  affecting existing rows

---

## Funding Rate Variant

Funding rates follow the same stages with a different column set:

```
exchange, symbol, timestamp, rate, predicted_rate, next_funding_time, source
```

And a different path:

```
data/{exchange}/{symbol}/funding_rate/{date}.parquet
```

The merge key omits `timeframe` (funding rates have no timeframe field).

---

## CLI integration

The `--merge-strategy` option is exposed on `cmpd fetch`:

```
cmpd fetch --help

  --merge-strategy TEXT  Row merge strategy: auto (default), memory, or duckdb
```

It flows through: `CLI → OhlcvService.ingest() → write_candles() → _merge_tables()`.
