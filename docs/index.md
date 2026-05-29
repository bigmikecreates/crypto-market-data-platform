# Crypto Market Data Platform

Local-first cryptocurrency market data ingestion, validation, storage, and
query. Candles and funding rates are modelled as string fields for memory
efficiency, converted to `decimal128` Parquet at write time via C++ `.cast()`.
Pluggable providers, layered validation, Typer CLI, DuckDB query engine,
FastAPI server, and a staged benchmark pipeline.

## What problem does it solve?

Market data ingestion looks simple — call an API, get a JSON array, write it
to a file. But production-grade ingestion requires:

- **Provider abstraction** — every exchange has a different API shape, field
  ordering, rate limit, and data quality profile
- **Validation at boundaries** — malformed candles should be caught before
  they reach storage, not during analysis
- **Measured performance** — knowing whether you are CPU-bound or
  network-bound determines what to optimise
- **No vendor lock-in** — data in portable Parquet format, queryable via
  DuckDB without a server, inspectable by any Parquet-compatible tool

This platform solves those problems while remaining deliberately scoped:
it ingests, validates, stores, and serves — it is not a trading bot,
dashboard, or strategy engine.

## Who is it for?

- Data engineers evaluating a local-first market data pipeline
- Quant researchers who need reproducible, validated market data
- Developers integrating cryptocurrency exchange APIs who want a
  proven abstraction pattern

## Maturity

Pre-production. Core data types and ingestion paths are stable. Live providers
for Bitfinex and KuCoin are implemented and tested. The benchmark framework
is feature-complete. Remaining work focuses on provider coverage, CI
automation, and documentation.

## Architecture

```
Provider → Candle[]/FundingRate[] → validation → ParquetWriter → data/{exchange}/…
                                                                        ↓
CLI (cmpd) ──────→ OhlcvService ────────→ Parquet files
     │                                            │
     │                                    DuckDBQueryService
     │                                            │
     ├── datasets, candles get, funding get       │
     ├── query --sql                              │
     └── serve (uvicorn) ───→ FastAPI ───→ REST endpoints

Benchmark (scripts/benchmark_pipeline.py) ───→ synthetic + live provider profiles
```

## Quickstart

```bash
# Install
pip install -e .

# Fetch fake data
cmpd fetch --start 2026-01-01 --end 2026-01-02

# Query it back
cmpd query ohlcv --limit 5

# Inspect a parquet file
cmpd inspect --path data --limit 5

# Start the API server
cmpd serve --port 8000

# Benchmark the pipeline
python scripts/benchmark_pipeline.py --count 10000

# Profile a live provider
python scripts/benchmark_pipeline.py profile --provider bitfinex
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `fetch` | Ingest market data (OHLCV or funding-rate) |
| `datasets` | List available Parquet datasets |
| `inspect` | Inspect a Parquet file or dataset directory |
| `query ohlcv` | Query candle data with filters |
| `query funding-rate` | Query funding rate data with filters |
| `query sql` | Run raw SQL via DuckDB `read_parquet` |
| `serve` | Start the FastAPI REST server |

→ See [CLI Reference](/reference/#/cli) for full command options.
