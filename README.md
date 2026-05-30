# Crypto Market Data Platform

Local-first cryptocurrency market data ingestion, validation, storage, and
query. Candles and funding rates are modelled as string fields for memory
efficiency, converted to `decimal128` Parquet at write time via C++ `.cast()`.
Writes use row-level upsert merge — re-fetching an overlapping time range is
idempotent. Pluggable providers, layered validation, Typer CLI, DuckDB query
engine, FastAPI server, and a staged benchmark pipeline.

## Architecture

```
Provider → Candle[]/FundingRate[] → validation → ParquetWriter → data/{exchange}/…
                                                                      ↓
CLI (cmpd) ──────→ OhlcvService ───→ (merge) ──→ Parquet files
     │                                                  │
     │                                          DuckDBQueryService
     │                                                  │
     ├── datasets, inspect                              │
     ├── query ohlcv, query funding-rate, query sql     │
     └── serve (uvicorn) ───→ FastAPI ───→ REST endpoints

Benchmark (scripts/benchmark_pipeline.py) ───→ synthetic + live provider profiles
```

## CLI Reference

The binary is `cmpd` (installed as a console script via `pip install -e .`, or
run via `python -m cmpd.cli.main`):

| Command | Description |
|---------|-------------|
| `fetch` | Ingest market data (`--mdt ohlcv` or `funding-rate`; `--merge-strategy auto|memory|duckdb`) |
| `datasets` | List available Parquet datasets |
| `query ohlcv` | Query candle data with filters |
| `query funding-rate` | Query funding rate data with filters |
| `query sql` | Run raw SQL via DuckDB read_parquet |
| `inspect` | Inspect a Parquet file or dataset (`--path`, `--start`, `--end`, `--stats`, `--verbose`) |
| `serve` | Start the FastAPI REST server |

## Quickstart

```bash
# Install
.venv/bin/pip install -e .

# Fetch fake OHLCV data (with row-level merge on overlap)
cmpd fetch --provider fake

# Fetch funding rates
cmpd fetch --mdt funding-rate --symbol BTC/USDT --start 2026-05-27 --end 2026-05-28

# Inspect the output
cmpd inspect --path data/fake/ --limit 5 --stats

# Query it back
cmpd query ohlcv

# Fetch with DuckDB-based merge for large partitions
cmpd fetch --provider bitfinex --symbol BTC/USDT --start 2025-01-01 --end 2025-02-01 --merge-strategy duckdb

# Start the API server
cmpd serve --port 8000

# Or via Docker
docker build -t cmpd .
docker run -p 8000:8000 -v ./data:/app/data cmpd

# Benchmark the pipeline (10,000 candles)
python scripts/benchmark_pipeline.py --count 10000

# Profile a live provider
python scripts/benchmark_pipeline.py profile --provider bitfinex
```

## Key Concepts

- **Candle** / **FundingRate** — all numeric fields stored as `str`. Deferred
  conversion to `decimal128(38,10)` and `timestamp[s|us]` at write time.
- **Row-level upsert merge** — replaces blind `pa.concat_tables` append.
  Dual-path strategy: Python set merge for partitions < 50K rows, DuckDB SQL
  anti-join (`LEFT JOIN ... WHERE NULL UNION ALL`) for larger partitions.
  Re-fetching an overlapping range is idempotent.
- **Layered validation** — 4 boundaries (provider → service → storage → query),
  each with a single responsibility. 5+ provider-independent rules.
- **Pluggable providers** — Bitfinex, KuCoin, Bybit, Bitstamp, MEXC, and
  FakeProvider, all implementing the `MarketDataProvider` ABC.
- **Parquet viewer** — `cmpd inspect` with sample display, column statistics,
  timestamp-range filtering, and full metadata dump.
- **QueryService ABC** — separates domain interface from engine.
  `DuckDBQueryService` reads partitioned Parquet in place via DuckDB
  `read_parquet()`.
- **FastAPI server** — thin HTTP adapter over the ABC; CORS, global error
  handler, DI-injectable backend.
- **Benchmark** — synthetic (CPU-bound) and live-provider (network-bound)
  profiling with Network/CPU boundary analysis.

For detailed design decisions behind each choice, see the
[MKDocs documentation site](https://bigmikecreates.github.io/crypto-market-data-platform/).
