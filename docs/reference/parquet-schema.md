# Parquet Schema Reference

## Candle table

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
| `timeframe` | `string` (dictionary encoded) | |
| `source` | `string` (dictionary encoded) | |

## Funding rate table

| Column | Parquet type | Notes |
|--------|-------------|-------|
| `rate` | `decimal128(38, 10)` | |
| `predicted_rate` | `decimal128(38, 10)` | |
| `next_funding_time` | `timestamp[s]` or `timestamp[us]` | Controlled by `TimestampConfig` |
| `timestamp` | `timestamp[s]` or `timestamp[us]` | |
| `exchange` | `string` (dictionary encoded) | |
| `symbol` | `string` (dictionary encoded) | |
| `source` | `string` (dictionary encoded) | |

## `decimal128(38, 10)`

All numeric columns use a fixed `decimal128(38, 10)` type.

- Supports up to 38 significant digits with 10 fractional places
- Covers prices from `0.0000000001` to `9999999999999999999999999999.9999999999`
- Always 16 bytes regardless of precision/scale
- Fixed schema guarantees cross-ticker DuckDB `UNION` queries work without type mismatches

## Timestamp

Timestamp resolution is controlled by `TimestampConfig`:

| Resolution | Parquet type | String format |
|------------|-------------|---------------|
| `s` (default) | `timestamp[s]` | `%Y-%m-%dT%H:%M:%S` |
| `us` | `timestamp[us]` | `%Y-%m-%dT%H:%M:%S.%f` |

## Dictionary encoding

String columns (`exchange`, `symbol`, `timeframe`, `source`) use dictionary
encoding in Parquet. This is the default for PyArrow string columns and
provides significant compression for low-cardinality fields.

## Partition directory layout

Partitioning follows a hierarchical directory structure by exchange, symbol,
and timeframe:

```
data/
  {exchange}/
    {symbol}/
      {timeframe}/
        {date}.parquet         # candles (one file per date)
      funding_rate/
        {date}.parquet         # funding rates (one file per date)
```

The date component is derived from the earliest timestamp in each batch,
formatted as `YYYY-MM-DD`.
