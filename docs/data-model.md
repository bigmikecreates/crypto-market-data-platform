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

All numeric columns are written as `decimal128(38,10)` at the storage
boundary. This provides exact decimal arithmetic, native DuckDB sort/filter,
and a fixed schema independent of ticker price ranges.

→ See [Parquet Schema Reference](/reference/#/parquet-schema) for the full
column-type mapping, dictionary encoding details, and partition layout.

## Timestamp handling

Timestamps are stored as strings in the model (`"2026-05-27T12:00:00"`) and
converted to `timestamp[s]` or `timestamp[us]` at write time according to
`TimestampConfig`.

→ See `TimestampConfig` in the [Python API Reference](/reference/#/python-api)
for the full dataclass definition.

## Query-side normalisation

When reading back, returned data is normalised so the round-trip
(write `str` → store `decimal128` → read `str`) is transparent:

- `Decimal` → `str` (prices match the model type)
- `datetime` → ISO-8601 string (timestamps match the model type)
