# Parquet Schema Reference

---

## Candle table

### Schema

| Column | Parquet type | Dictionary encoded | Notes |
|--------|-------------|-------------------|-------|
| `exchange` | `string` | yes | |
| `symbol` | `string` | yes | |
| `timeframe` | `string` | yes | |
| `timestamp` | `timestamp[s]` or `timestamp[us]` | no | Controlled by `TimestampConfig` |
| `open` | `decimal128(38, 10)` | no | |
| `high` | `decimal128(38, 10)` | no | |
| `low` | `decimal128(38, 10)` | no | |
| `close` | `decimal128(38, 10)` | no | |
| `volume` | `decimal128(38, 10)` | no | |
| `source` | `string` | yes | |

### Example (PyArrow schema)

```python
import pyarrow as pa

schema = pa.schema([
    ("exchange", pa.utf8()),
    ("symbol", pa.utf8()),
    ("timeframe", pa.utf8()),
    ("timestamp", pa.timestamp("s")),
    ("open", pa.decimal128(38, 10)),
    ("high", pa.decimal128(38, 10)),
    ("low", pa.decimal128(38, 10)),
    ("close", pa.decimal128(38, 10)),
    ("volume", pa.decimal128(38, 10)),
    ("source", pa.utf8()),
])
```

---

## Funding rate table

### Schema

| Column | Parquet type | Dictionary encoded | Notes |
|--------|-------------|-------------------|-------|
| `exchange` | `string` | yes | |
| `symbol` | `string` | yes | |
| `timestamp` | `timestamp[s]` or `timestamp[us]` | no | |
| `rate` | `decimal128(38, 10)` | no | |
| `predicted_rate` | `decimal128(38, 10)` | no | |
| `next_funding_time` | `timestamp[s]` or `timestamp[us]` | no | Controlled by `TimestampConfig` |
| `source` | `string` | yes | |

---

## `decimal128(38, 10)`

All numeric columns use a fixed `decimal128(38, 10)` type.

### Properties

| Property | Value |
|----------|-------|
| Precision | 38 significant digits |
| Scale | 10 fractional places |
| Storage | 16 bytes per value (fixed-width) |
| Min positive | `0.0000000001` |
| Max value | `9999999999999999999999999999.9999999999` |

### Why this type?

- Fixed schema guarantees cross-ticker DuckDB `UNION` queries work without type mismatches
- 10 fractional places cover all major exchange price granularity (including illiquid altcoins)
- 38 digits of precision cover all current and foreseeable crypto price levels

---

## Timestamp

Timestamp resolution is controlled by `TimestampConfig`.

### Configuration

| Resolution | Parquet type | String format |
|------------|-------------|---------------|
| `s` (default) | `timestamp[s]` | `%Y-%m-%dT%H:%M:%S` |
| `us` | `timestamp[us]` | `%Y-%m-%dT%H:%M:%S.%f` |

---

## Dictionary encoding

String columns (`exchange`, `symbol`, `timeframe`, `source`) use dictionary encoding in Parquet. This is the default for PyArrow string columns and provides significant compression for low-cardinality fields.

---

## Partition directory layout

Partitioning follows a hierarchical directory structure by exchange, symbol, and timeframe.

### Layout

```
data/
  {exchange}/
    {symbol}/
      {timeframe}/
        {date}.parquet         # candles (one file per date)
      funding_rate/
        {date}.parquet         # funding rates (one file per date)
```

### Partition key

| Data type | Partition key | Example path |
|-----------|---------------|-------------|
| Candles | `exchange / symbol / timeframe | date` | `data/bitfinex/BTC/USD/1h/2026-05-27.parquet` |
| Funding rates | `exchange / symbol / funding_rate | date` | `data/bitfinex/BTC/USD/funding_rate/2026-05-27.parquet` |

The date component is derived from the earliest timestamp in each batch, formatted as `YYYY-MM-DD`.
