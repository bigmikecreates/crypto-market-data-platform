# Getting Started

This page walks through a complete ingestion workflow: installing the package, fetching candles from a live exchange, querying the stored data, and serving it over HTTP. All commands are shown as they would appear in a terminal.

## Prerequisites

- Python 3.12 or later
- A virtual environment (recommended)

## Installation

```bash
git clone https://github.com/bigmikecreates/crypto-market-data-platform.git
cd crypto-market-data-platform
pip install -e .
```

Verify the installation:

```bash
cmpd --help
```

## Step 1 — Fetch your first candles

The `FakeProvider` generates a single synthetic candle without any network access. It is the correct starting point for verifying that the pipeline is functional.

```bash
cmpd fetch \
  --mdt ohlcv \
  --symbol "BTC/USDT" \
  --timeframe 1h \
  --start 2026-01-01 \
  --end 2026-01-02 \
  --provider fake
```

Expected output:

```
Wrote 1 candle(s) for BTC/USDT to data/
```

The candle is written to `data/fake/BTC/USDT/1h/2026-01-01.parquet`.

## Step 2 — Inspect the stored data

`cmpd inspect` reads one or more Parquet files and prints schema, row count, and a sample:

```bash
cmpd inspect --path data --limit 3
```

```
Directory: data
Files: 1
Rows: 1

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

Sample (first 1):
  exchange │ symbol   │ timeframe │ timestamp           │ open │ high │ low │ close │ volume │ source
  ──────── │ ──────── │ ───────── │ ─────────────────── │ ──── │ ──── │ ─── │ ───── │ ────── │ ──────
  fake     │ BTC/USDT │ 1h        │ 2026-01-01T00:00:00 │ 100  │ 110  │ 90  │ 105   │ 10     │ fake
```

Note the schema: numeric columns are stored as `decimal128(38,10)`, not `float`. String columns use Parquet dictionary encoding.

## Step 3 — Query the data

`cmpd query ohlcv` runs a DuckDB query over all Parquet files under the data directory:

```bash
cmpd query ohlcv --symbol "BTC/USDT" --limit 5
```

Filter by exchange, symbol, timeframe, or time range:

```bash
cmpd query ohlcv \
  --exchange fake \
  --symbol "BTC/USDT" \
  --timeframe 1h \
  --start 2026-01-01 \
  --end 2026-01-02 \
  --limit 5
```

Run raw SQL directly via DuckDB:

```bash
cmpd query sql \
  "SELECT symbol, count(*) AS rows FROM read_parquet('data/**/*.parquet') GROUP BY symbol"
```

## Step 4 — Fetch from a live provider

Replace `fake` with a live provider name. The symbol format is exchange-specific (see [Providers](providers.md) for the mapping per exchange).

```bash
# Bitfinex — uses tBTCUSD notation
cmpd fetch \
  --mdt ohlcv \
  --symbol "tBTCUSD" \
  --timeframe 1h \
  --start 2026-05-01 \
  --end 2026-05-02 \
  --provider bitfinex
```

```bash
# KuCoin — uses BTC-USDT notation
cmpd fetch \
  --mdt ohlcv \
  --symbol "BTC-USDT" \
  --timeframe 1h \
  --start 2026-05-01 \
  --end 2026-05-02 \
  --provider kucoin
```

Re-fetching the same range is safe. The writer performs a row-level upsert using `(exchange, symbol, timeframe, source, timestamp)` as the merge key — identical rows are skipped, corrected rows replace the stored version, and new rows are appended.

## Step 5 — Fetch multiple symbols concurrently

Pass `--symbol` multiple times to ingest several symbols in a single command. Use `--workers` to control the number of concurrent fetches (default: 4):

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
```

Each symbol is dispatched to a separate thread. Because KuCoin's pipeline is network-bound (~30× Net/CPU ratio), three concurrent fetches complete in roughly the same wall-clock time as one sequential fetch.

## Step 6 — List available datasets

`cmpd datasets` prints a summary of all Parquet datasets under the data directory:

```bash
cmpd datasets
```

```
  candle          kucoin     BTC-USDT    1h    files=7  rows=168
  candle          kucoin     ETH-USDT    1h    files=7  rows=168
  candle          kucoin     SOL-USDT    1h    files=7  rows=168
  candle          fake       BTC/USDT    1h    files=1  rows=1
```

## Step 7 — Start the REST API server

`cmpd serve` starts a FastAPI server that exposes all stored data over HTTP:

```bash
cmpd serve --host 127.0.0.1 --port 8000 --path data
```

The server exposes these endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/datasets` | List available datasets |
| GET | `/candles` | Query candle data with filters |
| GET | `/funding-rates` | Query funding rate data with filters |
| GET | `/summary` | Row and file counts per dataset |
| POST | `/query` | Run raw SQL (SELECT/WITH only) |

Example:

```bash
curl "http://127.0.0.1:8000/candles?symbol=BTC-USDT&limit=3"
```

See the [HTTP API Reference](reference/http-api.md) for full endpoint documentation.

## Step 8 — Fetch funding rates

Funding rate ingestion uses the same `fetch` command with `--mdt funding-rate`:

```bash
cmpd fetch \
  --mdt funding-rate \
  --symbol "BTC/USDT" \
  --start 2026-01-01 \
  --end 2026-01-02 \
  --provider fake \
  --timeframe 1h
```

```bash
cmpd query funding-rate --symbol "BTC/USDT" --limit 5
```

## Next steps

- [Architecture](architecture.md) — how the pipeline layers fit together
- [CLI Reference](reference/cli.md) — all commands and options
- [Benchmark Design](benchmark-design.md) — how to measure pipeline performance
- [Providers](providers.md) — symbol formats and provider-specific notes
