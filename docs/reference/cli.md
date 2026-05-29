# CLI Reference

Entry point: `cmpd` (`crypto_market_data_platform.cli.main:app`)

## `cmpd fetch`

Fetch market data and write to partitioned Parquet.

### Usage

```bash
cmpd fetch --mdt {ohlcv,funding-rate} --symbol SYMBOL --timeframe TIMEFRAME \
    --start START --end END --provider PROVIDER \
    [--output DIR] [--merge-strategy {auto,memory,duckdb}]
```

### Options

| Option | Type | Default | Applies to | Description |
|--------|------|---------|------------|-------------|
| `--mdt` | `str` | required | `both` | Market data type: `ohlcv` or `funding-rate` |
| `--symbol` | `str` | required | `both` | Trading pair symbol. Always quote to prevent shell splitting. |
| `--timeframe` | `str` | required | `ohlcv` only | Candle timeframe (e.g. `1h`, `1d`) |
| `--start` | ISO-8601 | required | `both` | Start time. Formats: `2026-01-01` or `2026-01-01T00:00:00` |
| `--end` | ISO-8601 | required | `both` | End time |
| `--provider` | `str` | required | `ohlcv` only | Data provider: `fake`, `bitfinex`, `bitstamp`, `kucoin`, `bybit`, `mexc`. When `--mdt funding-rate`, this value is accepted but ignored — the provider is always `FakeProvider`. |
| `--output` | `str` | `"data"` | `both` | Base output directory |
| `--merge-strategy` | `str` | `"auto"` | `both` | Row merge strategy: `auto`, `memory`, or `duckdb` |

### Merge strategy

When the same partition is fetched twice, a naive append would produce duplicate rows. Each row is identified by a merge key:

- **Candles:** `(exchange, symbol, timeframe, source, timestamp)`
- **Funding rates:** `(exchange, symbol, source, timestamp)`

On write, existing rows in the target Parquet file are compared against incoming rows using the merge key. Three strategies control how this comparison runs:

| Strategy | Mechanism | Best for |
|----------|-----------|----------|
| `memory` | Python `set`-based dedup: builds a key index in memory, does a linear scan. | Partitions with fewer than 50,000 rows. |
| `duckdb` | SQL anti-join via DuckDB: `SELECT e.* FROM existing e LEFT JOIN incoming i ON ... WHERE i.key IS NULL UNION ALL SELECT * FROM incoming` | Partitions with 50,000+ rows. Avoids loading the full existing partition into Python memory. |
| `auto` | Dispatches to `memory` if the existing partition row count is below 50,000, otherwise to `duckdb`. | General use. Chosen as the default. |

**Why this approach?** The merge-key upsert makes ingestion idempotent — fetching the same range twice produces identical files. It is also self-healing: if a provider returns a corrected candle for an existing timestamp, the old value is replaced on the next fetch.

The `duckdb` variant was added (rather than always using `memory`) because the set-based approach loads the entire existing partition into a Python dict. For daily runs with years of data, the SQL anti-join keeps the working set inside DuckDB's engine instead.

### Examples

Success:

```bash
$ cmpd fetch --mdt ohlcv --symbol "BTC/USDT" --timeframe 1h \
    --start 2026-05-27 --end 2026-05-28 --provider fake
Wrote 1 candle(s) to data/
```

Error:

```bash
$ cmpd fetch --mdt ohlcv --symbol "BTC/USDT" --timeframe 1h \
    --start 2026-05-27 --end 2026-05-28 --provider nonexistent
Unknown provider 'nonexistent'. Available: fake, bitfinex, bitstamp, kucoin, bybit, mexc
```

---

## `cmpd datasets`

List available datasets grouped by type.

### Usage

```bash
cmpd datasets [--path DIR]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--path` | `str` | `"data"` | Base data directory |

### Examples

Success:

```bash
$ cmpd datasets
  candle          bitfinex   BTC         USD   files=4  rows=144
  candle          fake       BTC         USDT  files=1  rows=1
  candle          fake       BTC-USD     1h    files=1  rows=32
```

Error:

```bash
$ cmpd datasets --path /nonexistent
No parquet files found under /nonexistent/
```

---

## `cmpd inspect`

Inspect a Parquet file or dataset directory.

### Usage

```bash
cmpd inspect --path PATH [--limit N] [--start TS] [--end TS]
    [--stats] [--verbose]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--path` | `str` | required | Path to a `.parquet` file or dataset directory |
| `--limit`, `-n` | `int` | `10` | Max rows in sample |
| `--start` | ISO-8601 | — | Start of timestamp range, inclusive |
| `--end` | ISO-8601 | — | End of timestamp range, exclusive |
| `--stats` | `bool` | `False` | Show column statistics |
| `--verbose` | `bool` | `False` | Show full Parquet metadata |

### Examples

Success:

```bash
$ cmpd inspect --path data --limit 3
Directory: data
Files: 6
Rows: 177

Schema:
  exchange   string
  symbol     string
  timeframe  string
  timestamp  timestamp[ms]
  open       decimal128(38, 10)
  high       decimal128(38, 10)
  low        decimal128(38, 10)
  close      decimal128(38, 10)
  volume     decimal128(38, 10)
  source     string

Sample (first 3):
  exchange │ symbol  │ timeframe │ timestamp           │ open  │ high  │ low   │ close │ volume     │ source
  ──────── │ ─────── │ ───────── │ ─────────────────── │ ───── │ ───── │ ───── │ ───── │ ────────── │ ────────
  bitfinex │ BTC/USD │ 1h        │ 2024-01-01T00:00:00 │ 42331 │ 42591 │ 42331 │ 42522 │ 9.03426154 │ bitfinex
  bitfinex │ BTC/USD │ 1h        │ 2024-01-01T01:00:00 │ 42509 │ 42811 │ 42482 │ 42678 │ 21.5892983 │ bitfinex
  bitfinex │ BTC/USD │ 1h        │ 2024-01-01T02:00:00 │ 42661 │ 42684 │ 42561 │ 42626 │ 5.41750572 │ bitfinex
```

Error:

```bash
$ cmpd inspect --path /nonexistent
Error: Path does not exist: /nonexistent
```

---

## `cmpd serve`

Start the FastAPI REST server.

### Usage

```bash
cmpd serve [--host ADDR] [--port N] [--path DIR]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--host` | `str` | `"127.0.0.1"` | Bind address |
| `--port`, `-p` | `int` | `8000` | Bind port |
| `--path` | `str` | `"data"` | Base data directory |

### Examples

Success:

```bash
$ cmpd serve --host 127.0.0.1 --port 8000
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Error:

```bash
$ cmpd serve --port 1
Error: [Errno 13] Permission denied
```

---

## `cmpd query`

Query stored datasets.

#### `cmpd query ohlcv`

Query candle data.

##### Usage

```bash
cmpd query ohlcv [--path DIR] [--exchange EXCH] [--symbol SYM]
    [--timeframe TF] [--start TS] [--end TS] [--limit N]
```

##### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--path` | `str` | `"data"` | Base data directory |
| `--exchange` | `str` | — | Filter by exchange |
| `--symbol` | `str` | — | Filter by symbol |
| `--timeframe` | `str` | — | Filter by timeframe |
| `--start` | ISO-8601 | — | Start timestamp (inclusive) |
| `--end` | ISO-8601 | — | End timestamp (exclusive) |
| `--limit`, `-n` | `int` | `10` | Max rows |

##### Examples

Success:

```bash
$ cmpd query ohlcv --exchange fake --symbol "BTC/USDT" --limit 3
  exchange | symbol | timeframe | timestamp | open | high | low | close | volume | source
  ---------------------------------------------------------------------------------------
  fake | BTC/USDT | 1h | 2026-05-27T00:00:00 | 100.0000000000 | 110.0000000000 | 90.0000000000 | 105.0000000000 | 10.0000000000 | fake
  (1 row(s))
```

Error:

```bash
$ cmpd query ohlcv --exchange nonexistent --symbol "NONEXISTENT"
(no results)
```

#### `cmpd query funding-rate`

Query funding rate data.

##### Usage

```bash
cmpd query funding-rate [--path DIR] [--exchange EXCH] [--symbol SYM]
    [--start TS] [--end TS] [--limit N]
```

##### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--path` | `str` | `"data"` | Base data directory |
| `--exchange` | `str` | — | Filter by exchange |
| `--symbol` | `str` | — | Filter by symbol |
| `--start` | ISO-8601 | — | Start timestamp (inclusive) |
| `--end` | ISO-8601 | — | End timestamp (exclusive) |
| `--limit`, `-n` | `int` | `10` | Max rows |

##### Examples

Success:

```bash
$ cmpd query funding-rate --exchange fake --symbol "BTC/USDT" --limit 3
  exchange | symbol | timestamp | rate | predicted_rate | next_funding_time | source
  ----------------------------------------------------------------------------------
  fake | BTC/USDT | 2026-05-27T00:00:00 | 0.0001000000 | 0.0002000000 | 2026-01-01T16:00:00 | fake
  (1 row(s))
```

Error:

```bash
$ cmpd query funding-rate --exchange nonexistent --symbol "NONEXISTENT"
(no results)
```

#### `cmpd query sql`

Run raw SQL via DuckDB.

##### Usage

```bash
cmpd query sql "SELECT ..." [--path DIR] [--limit N]
```

##### Options

| Parameter | Type | Position | Default | Description |
|-----------|------|----------|---------|-------------|
| `sql` | `str` | positional | required | SQL query |
| `--path` | `str` | named | `"data"` | Base data directory |
| `--limit`, `-n` | `int` | named | `100` | Max rows |

Use `read_parquet('data/**/*.parquet')` to query all stored data.

##### Examples

Success:

```bash
$ cmpd query sql "SELECT * FROM read_parquet('data/**/*.parquet') LIMIT 2"
  exchange | symbol | timeframe | timestamp | open | high | low | close | volume | source
  ---------------------------------------------------------------------------------------
  bitfinex | BTC/USD | 1h | 2024-01-01T00:00:00 | 42331.0000000000 | 42591.0000000000 | 42331.0000000000 | 42522.0000000000 | 9.0342615400 | bitfinex
  bitfinex | BTC/USD | 1h | 2024-01-01T01:00:00 | 42509.0000000000 | 42811.0000000000 | 42482.0000000000 | 42678.0000000000 | 21.5892983000 | bitfinex
  (2 row(s))
```

Error:

```bash
$ cmpd query sql "SELECT * FROM nonexistent"
CatalogException: Catalog Error: Table with name nonexistent does not exist!
```

---

See [Python API Reference](python-api.md) for provider classes, symbol mappings, URL endpoints, and rate-limit configuration.
