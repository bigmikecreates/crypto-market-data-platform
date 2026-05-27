# Data Model

## Entities

### Candle

```python
@dataclass(slots=True)
class Candle:
    exchange: str
    symbol: str
    timeframe: str
    timestamp: str
    open: str
    high: str
    low: str
    close: str
    volume: str
    source: str
```

### FundingRate

```python
@dataclass(slots=True)
class FundingRate:
    exchange: str
    symbol: str
    timestamp: str
    rate: str
    predicted_rate: str
    next_funding_time: str
    source: str
```

## Why strings for numeric fields?

Every numeric field (`open`, `high`, `low`, `close`, `volume`, `rate`, etc.) is
stored as `str`, not `Decimal` or `float`.

Reason | Detail
-------|-------
Memory | `str` objects are ~50 B vs ~120 B for `Decimal` — ~68 % saving per field. With 5 numeric fields per candle, this is ~350 B saved per object.
Zero transient Decimals | String-to-decimal128 conversion happens at write time via PyArrow's C++ `.cast()`. No Python `Decimal` objects are created on the write path.
Lightweight validation | Validation checks (regex format match, decimal string comparison via `_decimal_gte()`) operate directly on strings. No parse-and-allocate round-trip.

## Parquet schema

All numeric columns are written as `decimal128(38,10)`:

| Column | Parquet type | Notes |
|--------|-------------|-------|
| `open` | `decimal128(38, 10)` | |
| `high` | `decimal128(38, 10)` | |
| `low` | `decimal128(38, 10)` | |
| `close` | `decimal128(38, 10)` | |
| `volume` | `decimal128(38, 10)` | |
| `timestamp` | `timestamp[s]` or `timestamp[us]` | Controlled by `TimestampConfig` |
| `exchange` | `string` (dictionary encoded) | |
| `symbol` | `string` (dictionary encoded) | |
| `timeframe` | `string` (dictionary encoded) | Candle only |
| `rate` | `decimal128(38, 10)` | Funding rate only |
| `predicted_rate` | `decimal128(38, 10)` | Funding rate only |
| `next_funding_time` | `timestamp[s]` | Funding rate only |
| `source` | `string` (dictionary encoded) | |

`decimal128(38,10)` supports up to 38 significant digits with 10 fractional
places — covering prices from `0.0000000001` to `9999999999999999999999999999.9999999999`.
Since `decimal128` is always 16 bytes regardless of precision/scale, a fixed
schema costs nothing and guarantees cross-ticker DuckDB `UNION` queries work
without type mismatches.

## Timestamp handling

Timestamps are stored as strings in the model (`"2026-05-27T12:00:00"`) and
converted to `timestamp[s]` or `timestamp[us]` at write time. Resolution is
controlled by `TimestampConfig`:

```python
@dataclass(slots=True)
class TimestampConfig:
    resolution: str = "s"  # "s" or "us"
```

The `_to_timestamp()` function casts string arrays to the configured type
via PyArrow `.cast()`.

## Query-side normalisation

When reading back, `DuckDBQueryService._rows_to_dicts()` converts:

- `Decimal` → `str`  (so prices match the model type)
- `datetime` → ISO-8601 string (so timestamps match the model type)

This ensures the round-trip (write `str` → store `decimal128` → read `str`)
is transparent to the consumer.
