# CrMD Platform

A local-first pipeline for ingesting, validating, storing, and querying cryptocurrency market data. Exchange API responses are mapped to `Candle` and `FundingRate` records, validated at explicit system boundaries, persisted as partitioned Parquet files, and exposed through a Typer CLI and a FastAPI REST server.

## System overview

```mermaid
graph TD
    classDef provider fill:#e8f5e9,stroke:#2e7d32;
    classDef write fill:#fff3e0,stroke:#e65100;
    classDef store fill:#e3f2fd,stroke:#1565c0;
    classDef read fill:#f3e5f5,stroke:#6a1b9a;

    subgraph Providers
        A[Exchange API] --> B[MarketDataProvider]
    end

    subgraph "Write Path — Candles"
        B --> C1["Candle<br/><i>all-string fields</i>"]
        C1 --> D1["validate_candle_batch()<br/>ValidationResult"]
        D1 -- "passed ✓" --> E1["candle_to_table()<br/>PyArrow table"]
        D1 -- "passed ✗" --> F1["ValueError<br/>no write"]
        E1 --> G1["write_candles()<br/>row-level upsert merge"]
    end

    subgraph "Write Path — Funding Rates"
        B --> C2["FundingRate<br/><i>all-string fields</i>"]
        C2 --> D2["validate_funding_rate_batch()<br/>ValidationResult"]
        D2 -- "passed ✓" --> E2["funding_rate_to_table()<br/>PyArrow table"]
        D2 -- "passed ✗" --> F2["ValueError<br/>no write"]
        E2 --> G2["write_funding_rates()<br/>row-level upsert merge"]
    end

    subgraph Storage
        H1["data/{exchange}/{symbol}/{tf}/{date}.parquet"]
        H2["data/{exchange}/{symbol}/funding_rate/{date}.parquet"]
        G1 --> H1
        G2 --> H2
    end

    subgraph "Read Path"
        H1 --> I[DuckDBQueryService]
        H2 --> I
        I --> J[CLI — crmd query]
        I --> K[API — /candles, /funding-rates]
    end

    class A,B provider;
    class C1,D1,E1,F1,G1,C2,D2,E2,F2,G2 write;
    class H1,H2 store;
    class I,J,K read;
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

Core ingestion and query paths are stable. Providers: Bitfinex, KuCoin, Bybit, MEXC, Bitstamp, FakeProvider. The benchmark framework is feature-complete.

## Navigation

| Section | Purpose |
|---|---|
| [Getting Started](getting-started.md) | End-to-end walkthrough for new users |
| [Architecture](architecture.md) | Layer responsibilities and key design decisions |
| [Data Model](data-model.md) | `Candle` and `FundingRate` schema; why strings |
| [Providers](providers.md) | Supported exchanges, symbol mappings, adding new providers |
| [Validation Strategy](validation-strategy.md) | Validation boundaries and rule set |
| [Storage: Write Path](storage-e2e.md) | Stage-by-stage write pipeline |
| [Benchmarking](benchmark-design.md) | How the benchmark works, baseline metrics, and provider profiles |
