# Crypto Market Data Platform

Local-first cryptocurrency market data ingestion, validation, storage, and
query. Candles and funding rates are modelled as string fields for memory
efficiency, converted to `decimal128` Parquet at write time via C++ `.cast()`.
Pluggable providers, layered validation, Typer CLI, DuckDB query engine,
FastAPI server, and a staged benchmark pipeline.

## Architecture

```
Provider → Candle[]/FundingRate[] → validation → ParquetWriter → data/{exchange}/…
                                                                      ↓
CLI (cmpd) ──────→ IngestionService ────────→ Parquet files
     │                                            │
     │                                    DuckDBQueryService
     │                                            │
     ├── datasets, candles get, funding get       │
     ├── query --sql                              │
     └── serve (uvicorn) ───→ FastAPI ───→ REST endpoints

Benchmark (scripts/benchmark_pipeline.py) ───→ synthetic + live provider profiles
```

## Package Layout

```
src/crypto_market_data_platform/
├── __init__.py
├── config.py                 # TimestampConfig
├── models/
│   ├── candle.py             # Candle @dataclass(slots=True), all fields str
│   └── funding_rate.py       # FundingRate @dataclass(slots=True)
├── providers/
│   ├── base.py               # MarketDataProvider ABC
│   ├── fake.py               # FakeProvider (hardcoded candles + funding rates)
│   ├── bitfinex.py           # BitfinexProvider (live)
│   └── kucoin.py             # KuCoinProvider (live)
├── validation/
│   ├── result.py             # ValidationResult, Issue
│   ├── candles.py            # validate_candle_batch() + 5 rules
│   ├── funding_rates.py      # validate_funding_rate_batch() + rules
│   └── patterns.py           # Shared decimal/timestamp patterns
├── storage/
│   └── parquet_writer.py     # write_candles(), write_funding_rates()
├── cli/
│   ├── main.py               # cmpd Typer app (7 commands)
│   ├── ingestion_service.py  # IngestionService orchestrator
│   └── funding_ingestion_service.py
├── query/
│   ├── service.py            # QueryService ABC (5 methods)
│   └── duckdb_service.py     # DuckDBQueryService (read_parquet)
├── server/
│   ├── app.py                # create_app() factory
│   ├── config.py             # ServerConfig
│   ├── dependencies.py       # FastAPI Depends for QueryService
│   └── routers/
│       ├── health.py         # GET /health
│       ├── datasets.py       # GET /datasets
│       ├── candles.py        # GET /candles
│       ├── funding.py        # GET /funding-rates
│       ├── summary.py        # GET /summary
│       └── query.py          # POST /query
└── benchmark/
    ├── core.py               # PipelineRunner ABC, BenchmarkContext
    ├── rules.py              # CrossValidationRule engine
    └── runners.py            # Candle + Provider pipeline runners

scripts/
├── benchmark_pipeline.py     # Typer CLI: run (synthetic), profile (live)
└── …

Dockerfile                    # uvicorn CMD for server deployment
docs/
├── benchmarks/
│   └── design-rationale.md   # All design decisions with evidence
├── validation-strategy.md
├── provider-selection.md
├── lessons-from-bitfinex-integration.md
├── lessons-from-kucoin-integration.md
└── next-steps.md
```

## CLI Reference

The binary is `cmpd` (run via `python -m crypto_market_data_platform.cli.main`):

| Command | Description |
|---------|-------------|
| `fetch` | Ingest OHLCV candles from a provider |
| `fetch-funding` | Ingest funding rates (FakeProvider only) |
| `datasets` | List available Parquet datasets |
| `candles get` | Query candle data with filters |
| `funding get` | Query funding rate data with filters |
| `query --sql` | Run raw SQL via DuckDB read_parquet |
| `serve` | Start the FastAPI REST server |

## Quickstart

```bash
# Install
.venv/bin/pip install -e .

# Fetch fake data
python -m crypto_market_data_platform.cli.main fetch --provider fake

# Query it back
python -m crypto_market_data_platform.cli.main candles get

# Start the API server
python -m crypto_market_data_platform.cli.main serve --port 8000

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
- **Layered validation** — 4 boundaries (provider → service → storage → query),
  each with a single responsibility. 5+ provider-independent rules.
- **QueryService ABC** — separates domain interface from engine.
  `DuckDBQueryService` reads partitioned Parquet in place via DuckDB
  `read_parquet()`.
- **FastAPI server** — thin HTTP adapter over the ABC; CORS, global error
  handler, DI-injectable backend.
- **Benchmark** — synthetic (CPU-bound) and live-provider (network-bound)
  profiling with Network/CPU boundary analysis.

For detailed design decisions behind each choice, see
[`docs/benchmarks/design-rationale.md`](docs/benchmarks/design-rationale.md).
