# CLI Reference

Entry point: `cmpd` — installed by `pip install -e .` and wired to `cmpd.cli.main:app`.

---

## `cmpd fetch`

Fetch market data from a provider and write to partitioned Parquet. Validates all records before writing; fails without writing if validation does not pass.

### Usage

```bash
cmpd fetch \
  --mdt {ohlcv,funding-rate} \
  --symbol SYMBOL [--symbol SYMBOL ...] \
  --timeframe TIMEFRAME \
  --start START \
  --end END \
  --provider PROVIDER \
  [--output DIR] \
  [--merge-strategy {auto,memory,duckdb}] \
  [--workers N]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--mdt` | `str` | required | Market data type: `ohlcv` or `funding-rate` |
| `--symbol` | `str` (repeatable) | required | Trading pair symbol. Repeat the flag for multiple symbols: `--symbol BTC-USDT --symbol ETH-USDT`. Always quote symbols containing `/`. |
| `--timeframe` | `str` | required | Candle timeframe: `1m`, `5m`, `15m`, `1h`, `4h`, `1d`. Provider support varies. |
| `--start` | ISO-8601 | required | Start of the requested range. Formats: `2026-01-01` or `2026-01-01T00:00:00`. |
| `--end` | ISO-8601 | required | End of the requested range (exclusive at the provider level; exact semantics vary by exchange). |
| `--provider` | `str` | required | Provider name: `fake`, `bitfinex`, `bitstamp`, `kucoin`, `bybit`, `mexc`. Ignored when `--mdt funding-rate` (always `FakeProvider`). |
| `--output` | `str` | `"data"` | Base output directory. Parquet files are written under `{output}/{exchange}/{symbol}/{timeframe}/{date}.parquet`. |
| `--merge-strategy` | `str` | `"auto"` | Row merge strategy for existing partitions. See [Merge strategy](#merge-strategy) below. |
| `--workers` | `int` | `4` | Number of concurrent symbol fetches. Applies when multiple `--symbol` values are given. Range: 1–32. |

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

When multiple `--symbol` values are provided, `cmpd fetch` dispatches each symbol to a separate thread using `ThreadPoolExecutor(max_workers=workers)`. Each thread constructs its own provider instance and writes to a distinct partition path, so there are no write conflicts.

For network-bound providers (KuCoin: ~30x Net/CPU ratio, Bitfinex: ~6x), concurrent fetches reduce wall-clock time proportionally to the number of workers, since each thread spends most of its time waiting on HTTP responses rather than executing Python.

### Examples

Single symbol, fake provider:

```bash
cmpd fetch \
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
cmpd fetch \
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
cmpd fetch \
  --mdt funding-rate \
  --symbol "BTC/USDT" \
  --timeframe 1h \
  --start 2026-01-01 \
  --end 2026-01-02 \
  --provider fake
# Wrote 1 funding rate(s) for BTC/USDT to data/
```

Unknown provider:

```bash
cmpd fetch --mdt ohlcv --symbol "BTC/USDT" --timeframe 1h \
    --start 2026-01-01 --end 2026-01-02 --provider nonexistent
# Unknown provider 'nonexistent'. Available: fake, bitfinex, bitstamp, kucoin, bybit, mexc
```

---

## `cmpd datasets`

List all Parquet datasets under the data directory, grouped by type.

### Usage

```bash
cmpd datasets [--path DIR]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--path` | `str` | `"data"` | Base data directory |

### Examples

```bash
cmpd datasets
  candle          kucoin     BTC-USDT    1h    files=7  rows=168
  candle          kucoin     ETH-USDT    1h    files=7  rows=168
  candle          fake       BTC/USDT    1h    files=1  rows=1
```

```bash
cmpd datasets --path /nonexistent
# No parquet files found under /nonexistent/
```

---

## `cmpd inspect`

Read one or more Parquet files and print schema, row count, and a data sample. Accepts either a single `.parquet` file or a directory (scanned recursively).

### Usage

```bash
cmpd inspect --path PATH [--limit N] [--start TS] [--end TS] [--stats] [--verbose]
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
cmpd inspect --path data --limit 3
# Directory: data
# Files: 1  Rows: 1
# Schema:
#   exchange   string
#   symbol     string
#   ...
```

```bash
cmpd inspect --path data/kucoin/BTC-USDT/1h/2026-05-01.parquet --stats
```

---

## `cmpd query ohlcv`

Query stored candle data using DuckDB. All filters are applied as SQL predicates over the partitioned Parquet files.

### Usage

```bash
cmpd query ohlcv [--path DIR] [--exchange EXCH] [--symbol SYM]
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
cmpd query ohlcv --symbol "BTC-USDT" --timeframe 1h --limit 3
  exchange | symbol   | timeframe | timestamp           | open   | ...
  -------- | -------- | --------- | ------------------- | ------ | ...
  kucoin   | BTC-USDT | 1h        | 2026-05-01T00:00:00 | 94800  | ...
  (3 row(s))
```

No match returns `(no results)` and exits 0.

---

## `cmpd query funding-rate`

Query stored funding rate data.

### Usage

```bash
cmpd query funding-rate [--path DIR] [--exchange EXCH] [--symbol SYM]
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
cmpd query funding-rate --symbol "BTC/USDT" --limit 3
  exchange | symbol   | timestamp           | rate         | predicted_rate | ...
  -------- | -------- | ------------------- | ------------ | -------------- | ...
  fake     | BTC/USDT | 2026-01-01T00:00:00 | 0.0001000000 | 0.0002000000   | ...
  (1 row(s))
```

---

## `cmpd query sql`

Execute a raw SQL query over stored Parquet files using DuckDB. Only `SELECT` and `WITH ... SELECT` statements are permitted; `COPY`, `CREATE`, `DROP`, `INSTALL`, and other write or extension commands are blocked at the server level and in the CLI wrapper.

### Usage

```bash
cmpd query sql "SELECT ..." [--path DIR] [--limit N]
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
cmpd query sql "SELECT symbol, count(*) AS rows FROM read_parquet('data/**/*.parquet') GROUP BY symbol"
  symbol   | rows
  -------- | ----
  BTC-USDT | 168
  ETH-USDT | 168
```

```bash
cmpd query sql "DROP TABLE t"
# Error: Only SELECT (or WITH ... SELECT) statements are permitted.
```

---

## `cmpd serve`

Start the FastAPI REST server. The server exposes the same query surface as the CLI over HTTP and accepts a `path` query parameter on each request to override the base data directory.

### Usage

```bash
cmpd serve [--host ADDR] [--port N] [--path DIR]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--host` | `str` | `"127.0.0.1"` | Bind address |
| `--port`, `-p` | `int` | `8000` | Bind port |
| `--path` | `str` | `"data"` | Default base data directory |

### Examples

```bash
cmpd serve --host 127.0.0.1 --port 8000
# INFO:     Started server process [12345]
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

→ See [HTTP API Reference](http-api.md) for endpoint documentation.

---

See [Python API Reference](python-api.md) for provider classes, symbol conventions, URL endpoints, and rate-limit configuration.
