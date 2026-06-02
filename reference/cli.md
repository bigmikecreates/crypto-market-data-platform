# CLI Reference

Entry point: `crmd` — installed by `pip install -e .` and wired to `crmd_platform.cli.main:app`.

---

## `crmd fetch`

Fetch market data from a provider and write to partitioned Parquet. Validates all records before writing; fails without writing if validation does not pass.

### Usage

```bash
crmd fetch \
  --mdt {ohlcv,funding-rate} \
  --symbol SYMBOL [--symbol SYMBOL ...] \
  --timeframe TIMEFRAME \
  { --start START | --since-last } \
  [--end END] \
  --provider PROVIDER \
  [--output DIR] \
  [--merge-strategy {auto,memory,duckdb}] \
  [--workers N] \
  [--follow SECONDS]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--mdt` | `str` | required | Market data type: `ohlcv` or `funding-rate` |
| `--symbol` | `str` (repeatable) | required | Trading pair symbol. Repeat the flag for multiple symbols: `--symbol BTC-USDT --symbol ETH-USDT`. Always quote symbols containing `/`. |
| `--timeframe` | `str` | required | Candle timeframe: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`. Provider support varies. |
| `--start` | ISO-8601 | — | Start of the requested range. Formats: `2026-01-01` or `2026-01-01T00:00:00`. Mutually exclusive with `--since-last`; one of the two is required. |
| `--end` | ISO-8601 | now | End of the requested range. Defaults to current UTC time when omitted. |
| `--provider` | `str` | required | Provider name: `fake`, `bitfinex`, `bitstamp`, `kucoin`, `bybit`, `mexc`. Ignored when `--mdt funding-rate` (always `FakeProvider`). |
| `--output` | `str` | `"data"` | Base output directory or `az://container/prefix` URI. Parquet files are written under `{output}/{exchange}/{symbol}/{timeframe}/{date}.parquet`. |
| `--merge-strategy` | `str` | `"auto"` | Row merge strategy for existing partitions. See [Merge strategy](#merge-strategy) below. |
| `--workers` | `int` | `4` | Number of concurrent symbol fetches. Applies when multiple `--symbol` values are given. Range: 1–32. |
| `--since-last` | flag | `False` | Auto-detect `--start` from the last stored candle for each symbol (scoped to the chosen provider). Mutually exclusive with `--start`. Combine with `--follow` for continuous ingestion. |
| `--follow` | `int` | — | After each fetch, sleep N seconds then fetch again. Use with `--since-last` to keep data continuously current. Transient per-symbol errors are logged but do not stop the loop. |

### Merge strategy

When a partition file for the requested date already exists, the writer performs a row-level upsert rather than overwriting or appending blindly. Each row is identified by its merge key:

- **Candles:** `(exchange, symbol, timeframe, source, timestamp)`
- **Funding rates:** `(exchange, symbol, source, timestamp)`

Incoming rows are merged against existing rows: identical rows are skipped, rows whose key matches but values differ replace the existing row, and rows with no matching key are appended.

| Strategy | Mechanism | Use when |
|---|---|---|
| `memory` | Python `dict`-based key index over the existing table | Partitions with fewer than 50,000 existing rows |
| `duckdb` | SQL `NOT EXISTS` anti-join via DuckDB: existing rows not present in incoming are kept; all incoming rows are appended | Partitions with 50,000 or more existing rows |
| `auto` | Dispatches to `memory` below 50,000 rows, `duckdb` at or above | General use (default) |

This merge makes ingestion **idempotent** — fetching the same range twice produces identical files — and **self-healing** — a corrected candle from the provider replaces the stale stored value on the next fetch.

### Concurrent symbol fetching

When multiple `--symbol` values are provided, `crmd fetch` dispatches each symbol to a separate thread using `ThreadPoolExecutor(max_workers=workers)`. Each thread constructs its own provider instance and writes to a distinct partition path, so there are no write conflicts.

For network-bound providers (KuCoin: ~30x Net/CPU ratio, Bitfinex: ~6x), concurrent fetches reduce wall-clock time proportionally to the number of workers, since each thread spends most of its time waiting on HTTP responses rather than executing Python.

### Examples

Single symbol, fake provider:

```bash
crmd fetch \
  --mdt ohlcv \
  --symbol "BTC/USDT" \
  --timeframe 1h \
  --start 2026-01-01 \
  --end 2026-01-02 \
  --provider fake
# Wrote 1 candle(s) for BTC/USDT to data/
```

Multiple symbols, live provider, 3 workers:

```bash
crmd fetch \
  --mdt ohlcv \
  --symbol "BTC-USDT" \
  --symbol "ETH-USDT" \
  --symbol "SOL-USDT" \
  --timeframe 1h \
  --start 2026-05-01 \
  --end 2026-05-08 \
  --provider kucoin \
  --workers 3
# Wrote 168 candle(s) for BTC-USDT to data/
# Wrote 168 candle(s) for ETH-USDT to data/
# Wrote 168 candle(s) for SOL-USDT to data/
```

Funding rates:

```bash
crmd fetch \
  --mdt funding-rate \
  --symbol "BTC/USDT" \
  --timeframe 1h \
  --start 2026-01-01 \
  --end 2026-01-02 \
  --provider fake
# Wrote 1 funding rate(s) for BTC/USDT to data/
```

Continuous ingestion with `--since-last` and `--follow`:

```bash
# First run: seed with an explicit start date
crmd fetch \
  --mdt ohlcv \
  --symbol "BTC-USDT" \
  --symbol "ETH-USDT" \
  --timeframe 1h \
  --start 2026-01-01 \
  --provider kucoin

# Subsequent runs: auto-advance from last stored candle, poll every 5 minutes
crmd fetch \
  --mdt ohlcv \
  --symbol "BTC-USDT" \
  --symbol "ETH-USDT" \
  --timeframe 1h \
  --provider kucoin \
  --since-last \
  --follow 300
# Wrote 3 candle(s) for BTC-USDT to data/
# Wrote 3 candle(s) for ETH-USDT to data/
# Sleeping 300s before next fetch...
```

Unknown provider:

```bash
crmd fetch --mdt ohlcv --symbol "BTC/USDT" --timeframe 1h \
    --start 2026-01-01 --end 2026-01-02 --provider nonexistent
# Unknown provider 'nonexistent'. Available: fake, bitfinex, bitstamp, kucoin, bybit, mexc
```

---

## `crmd datasets`

List all Parquet datasets under the data directory, grouped by type.

### Usage

```bash
crmd datasets [--path DIR]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--path` | `str` | `"data"` | Base data directory |

### Examples

```bash
crmd datasets
  candle          kucoin     BTC-USDT    1h    files=7  rows=168
  candle          kucoin     ETH-USDT    1h    files=7  rows=168
  candle          fake       BTC/USDT    1h    files=1  rows=1
```

```bash
crmd datasets --path /nonexistent
# No parquet files found under /nonexistent/
```

---

## `crmd inspect`

Read one or more Parquet files and print schema, row count, and a data sample. Accepts either a single `.parquet` file or a directory (scanned recursively).

### Usage

```bash
crmd inspect --path PATH [--limit N] [--start TS] [--end TS] [--stats] [--verbose]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--path` | `str` | required | Path to a `.parquet` file or dataset directory |
| `--limit`, `-n` | `int` | `10` | Maximum rows in the sample |
| `--start` | ISO-8601 | — | Filter sample to rows at or after this timestamp |
| `--end` | ISO-8601 | — | Filter sample to rows before this timestamp |
| `--stats` | flag | off | Show column-level statistics (min, max, null count) |
| `--verbose` | flag | off | Show full Parquet file metadata (row groups, compression, encoding) |

### Examples

```bash
crmd inspect --path data --limit 3
# Directory: data
# Files: 1  Rows: 1
# Schema:
#   exchange   string
#   symbol     string
#   ...
```

```bash
crmd inspect --path data/kucoin/BTC-USDT/1h/2026-05-01.parquet --stats
```

---

## `crmd query ohlcv`

Query stored candle data using DuckDB. All filters are applied as SQL predicates over the partitioned Parquet files.

### Usage

```bash
crmd query ohlcv [--path DIR] [--exchange EXCH] [--symbol SYM]
    [--timeframe TF] [--start TS] [--end TS] [--limit N]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--path` | `str` | `"data"` | Base data directory |
| `--exchange` | `str` | — | Filter by exchange name |
| `--symbol` | `str` | — | Filter by symbol |
| `--timeframe` | `str` | — | Filter by timeframe |
| `--start` | ISO-8601 | — | Return rows at or after this timestamp (inclusive) |
| `--end` | ISO-8601 | — | Return rows before this timestamp (exclusive) |
| `--limit`, `-n` | `int` | `10` | Maximum rows returned |

### Examples

```bash
crmd query ohlcv --symbol "BTC-USDT" --timeframe 1h --limit 3
  exchange | symbol   | timeframe | timestamp           | open   | ...
  -------- | -------- | --------- | ------------------- | ------ | ...
  kucoin   | BTC-USDT | 1h        | 2026-05-01T00:00:00 | 94800  | ...
  (3 row(s))
```

No match returns `(no results)` and exits 0.

---

## `crmd query funding-rate`

Query stored funding rate data.

### Usage

```bash
crmd query funding-rate [--path DIR] [--exchange EXCH] [--symbol SYM]
    [--start TS] [--end TS] [--limit N]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--path` | `str` | `"data"` | Base data directory |
| `--exchange` | `str` | — | Filter by exchange name |
| `--symbol` | `str` | — | Filter by symbol |
| `--start` | ISO-8601 | — | Return rows at or after this timestamp (inclusive) |
| `--end` | ISO-8601 | — | Return rows before this timestamp (exclusive) |
| `--limit`, `-n` | `int` | `10` | Maximum rows returned |

### Examples

```bash
crmd query funding-rate --symbol "BTC/USDT" --limit 3
  exchange | symbol   | timestamp           | rate         | predicted_rate | ...
  -------- | -------- | ------------------- | ------------ | -------------- | ...
  fake     | BTC/USDT | 2026-01-01T00:00:00 | 0.0001000000 | 0.0002000000   | ...
  (1 row(s))
```

---

## `crmd query sql`

Execute a raw SQL query over stored Parquet files using DuckDB. Only `SELECT` and `WITH ... SELECT` statements are permitted; `COPY`, `CREATE`, `DROP`, `INSTALL`, and other write or extension commands are blocked at the server level and in the CLI wrapper.

### Usage

```bash
crmd query sql "SELECT ..." [--path DIR] [--limit N]
```

### Options

| Parameter | Type | Position | Default | Description |
|---|---|---|---|---|
| `sql` | `str` | positional | required | SQL query string |
| `--path` | `str` | named | `"data"` | Base data directory |
| `--limit`, `-n` | `int` | named | `100` | Maximum rows returned |

Use `read_parquet('data/**/*.parquet')` to query all stored data across all exchanges and symbols.

### Examples

```bash
crmd query sql "SELECT symbol, count(*) AS rows FROM read_parquet('data/**/*.parquet') GROUP BY symbol"
  symbol   | rows
  -------- | ----
  BTC-USDT | 168
  ETH-USDT | 168
```

```bash
crmd query sql "DROP TABLE t"
# Error: Only SELECT (or WITH ... SELECT) statements are permitted.
```

---

## `crmd serve`

Start the FastAPI REST server. The data path is fixed at startup — callers cannot override it per request.

### Usage

```bash
crmd serve [--host ADDR] [--port N] [--path DIR] [--api-key KEY] [--cors-origins ORIGINS]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--host` | `str` | `"127.0.0.1"` | Bind address |
| `--port`, `-p` | `int` | `8000` | Bind port |
| `--path` | `str` | `"data"` | Storage root — a local path or `az://container/prefix`. All endpoints query this location. |
| `--api-key` | `str` | — | Require `X-API-Key: KEY` on all data endpoints. Also read from `CRMD_API_KEY` env var. Generate a key with: `python -c "import secrets; print(secrets.token_hex(32))"`. Omitting the flag runs the server in **open dev mode** (a warning is logged). |
| `--cors-origins` | `str` | `"http://localhost:3000,http://127.0.0.1:3000"` | Comma-separated list of allowed CORS origins. Also read from `CRMD_CORS_ORIGINS` env var. |

### Examples

Local dev (open, localhost only):

```bash
crmd serve --path data --port 8000
# WARNING: CRMD_API_KEY is not set — server running in open dev mode.
```

Secured for LAN or cloud exposure:

```bash
export CRMD_API_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
crmd serve --path az://mycontainer/crypto-data --port 8000
```

→ See [HTTP API Reference](http-api.md) for endpoint documentation including how to pass the `X-API-Key` header.

---

← [API Reference Overview](overview.md) · [Python API Reference](python-api.md) for provider classes, symbol conventions, URL endpoints, and rate-limit configuration.
