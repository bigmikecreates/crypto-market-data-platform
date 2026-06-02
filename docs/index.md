# Crypto Market Data Platform

A local-first pipeline for ingesting, validating, storing, and querying cryptocurrency market data. Exchange API responses are mapped to `Candle` and `FundingRate` records, validated at explicit system boundaries, persisted as partitioned Parquet files, and exposed through a Typer CLI and a FastAPI REST server.

## System overview

```mermaid
graph TD
    subgraph Providers
        A1[Exchange API] --> B1[OHLCVProvider]
        A2[Exchange API] --> B2[FundingRateProvider]
    end
    subgraph Write Path — Candles
        B1 --> C1["Candle\n(all-string fields)"]
        C1 --> D1["validate_candle_batch()\nValidationResult"]
        D1 -- "passed = True" --> E1["candle_to_table()\nPyArrow table"]
        D1 -- "passed = False" --> F1["ValueError — no write"]
        E1 --> G1["write_candles()\nRow-level upsert merge"]
    end
    subgraph Write Path — Funding Rates
        B2 --> C2["FundingRate\n(all-string fields)"]
        C2 --> D2["validate_funding_rate_batch()\nValidationResult"]
        D2 -- "passed = True" --> E2["funding_rate_to_table()\nPyArrow table"]
        D2 -- "passed = False" --> F2["ValueError — no write"]
        E2 --> G2["write_funding_rates()\nRow-level upsert merge"]
    end
    subgraph Storage
        H1["data/{exchange}/{symbol}/{tf}/{date}.parquet"]
        H2["data/{exchange}/{symbol}/funding_rate/{date}.parquet"]
        G1 --> H1
        G2 --> H2
    end
    subgraph Read Path
        H1 --> I[DuckDBQueryService]
        H2 --> I
        I --> J[CLI — crmd query]
        I --> K[FastAPI — /candles, /funding-rates]
    end
```

## Getting started

Install the package and run your first ingestion against the built-in `FakeProvider`:

```bash
pip install -e .

crmd fetch \
  --mdt ohlcv \
  --symbol "BTC/USDT" \
  --timeframe 1h \
  --start 2026-01-01 \
  --end 2026-01-02 \
  --provider fake

# Wrote 1 candle(s) for BTC/USDT to data/
```

Then inspect what was written and query it back:

```bash
crmd inspect --path data --limit 3

crmd query ohlcv --symbol "BTC/USDT" --limit 5
```

For a complete walkthrough — multiple providers, concurrent symbol ingestion, the REST API — see [Getting Started](getting-started.md).

## Design boundaries

| Boundary | What it enforces |
|---|---|
| Provider | Raw API response → typed `Candle` / `FundingRate` with all-string fields |
| Service | Batch validation (format, OHLC invariants, duplicates) — blocks write on failure |
| Storage | String → `decimal128(38,10)` cast, row-level upsert merge, Parquet write |
| Query | `read_parquet` via DuckDB, schema normalisation, result pagination |

## Current status

Core ingestion and query paths are stable. Providers: Bitfinex, KuCoin, Bybit, MEXC, Bitstamp, FakeProvider. The benchmark framework is feature-complete. See [Roadmap](roadmap.md) for planned work.

## Navigation

| Section | Purpose |
|---|---|
| [Getting Started](getting-started.md) | End-to-end walkthrough for new users |
| [Architecture](architecture.md) | Layer responsibilities and key design decisions |
| [Data Model](data-model.md) | `Candle` and `FundingRate` schema; why strings |
| [Providers](providers.md) | Supported exchanges, symbol mappings, adding new providers |
| [Validation Strategy](validation-strategy.md) | Validation boundaries and rule set |
| [Storage: Write Path](storage-e2e.md) | Stage-by-stage write pipeline |
| [Benchmark Design](benchmark-design.md) | How the benchmark is structured and what it measures |
| [Performance Notes](performance-notes.md) | Measured baseline metrics and provider profiles |
| [Roadmap](roadmap.md) | Completed work and planned improvements |
