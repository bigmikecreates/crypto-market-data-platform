<div align="center">

# CrMD Platform

[![CI](https://github.com/bigmikecreates/crypto-market-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/bigmikecreates/crypto-market-data-platform/actions/workflows/ci.yml)
[![codecov](https://codecov.io/github/bigmikecreates/crypto-market-data-platform/graph/badge.svg?token=CBJ67QDX5X)](https://codecov.io/github/bigmikecreates/crypto-market-data-platform)
[![Docs](https://img.shields.io/badge/docs-live-blue)](https://bigmikecreates.github.io/crypto-market-data-platform/)

A pipeline for ingesting, validating, storing, and querying cryptocurrency market data. Exchange API responses are mapped to typed records, validated at explicit service boundaries, persisted as partitioned Parquet files, and exposed through a CLI and a REST API.

</div>

---

## How it works

1. **Fetch** — Provider adapters call exchange APIs and map responses to `Candle` or `FundingRate` records (all fields are strings at this point)
2. **Validate** — Batch validation checks decimal format, OHLC invariants, duplicate timestamps, etc. If validation fails, the write is blocked entirely
3. **Store** — Valid records are cast to `decimal128(38,10)` and written as partitioned Parquet files (local filesystem or cloud object storage)
4. **Query** — DuckDB reads Parquet files in place via `read_parquet()`, exposed through CLI commands and a REST API

All numeric fields (`open`, `high`, `low`, `close`, `volume`) are stored as strings in the model layer and cast to `decimal128(38,10)` at write time via PyArrow's C++ `.cast()` kernel. Parquet files are the interchange format: portable, queryable by DuckDB without import, and readable by any Parquet-compatible tool.

---

## Quickstart

```bash
pip install -e .

# Fetch one candle from the built-in FakeProvider
crmd fetch \
  --mdt ohlcv \
  --symbol "BTC/USDT" \
  --timeframe 1h \
  --start 2026-01-01 \
  --end 2026-01-02 \
  --provider fake

# Inspect what was written
crmd inspect --path data --limit 5

# Query it back
crmd query ohlcv --symbol "BTC/USDT" --limit 5

# Start the REST API
crmd serve --port 8050
```

For a full walkthrough — live providers, concurrent symbol ingestion, the query API — see **[Getting Started](https://bigmikecreates.github.io/crypto-market-data-platform/getting-started/)**.

---

## Providers

| Provider | Symbol format | Notes |
|---|---|---|
| `fake` | Any | Synthetic candles, no network access. Use for pipeline testing. |
| `bitfinex` | `tBTCUSD` | 10,000-candle batch limit, non-standard field order. |
| `bitstamp` | `btcusd` | Dict-based response format. |
| `kucoin` | `BTC-USDT` | 1,500-candle server limit, second-precision timestamps. |
| `bybit` | `BTCUSDT` | Category-based dispatch (spot), descending sort order. |
| `mexc` | `BTCUSDT` | Standard field order, 500-candle limit. |
| `gateio` | `BTC_USDT` | Non-standard field order (volume, close, high, low, open). 8-field response rows. |

Each provider implements the `OHLCVProvider` or `FundingRateProvider` ABC. Adding a new exchange means implementing one method — no consumer code changes.

---

## CLI reference

| Command | Description |
|---|---|
| `fetch` | Ingest OHLCV or funding-rate data. Accepts multiple `--symbol` values with `--workers N` for concurrent fetches. |
| `datasets` | List all available Parquet datasets under the data directory. |
| `inspect` | Print schema, row count, and sample rows from a Parquet file or directory. |
| `query ohlcv` | Query candle data with exchange, symbol, timeframe, and time-range filters. |
| `query funding-rate` | Query funding rate data with filters. |
| `query sql` | Run raw `SELECT` SQL via DuckDB over stored Parquet files. |
| `serve` | Start the FastAPI REST server. |

→ Full option reference: [CLI Reference](https://bigmikecreates.github.io/crypto-market-data-platform/reference/cli/)

---

## Cloud storage

The pipeline supports multiple cloud storage backends through a unified `StorageBackend` abstraction. Switch between local, Azure, S3, or GCS by changing one flag:

### Azure Blob Storage

```bash
# Write to Azure
crmd fetch --provider kucoin --symbol BTC-USDT --timeframe 1h \
           --start 2026-01-01 --end 2026-01-08 \
           --output az://mycontainer/crypto-data

# Read from Azure
crmd query ohlcv --path az://mycontainer/crypto-data --symbol BTC-USDT
crmd serve       --path az://mycontainer/crypto-data --port 8050
```

Install the Azure extra and set credentials:

```bash
pip install -e ".[azure]"
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."
# or: AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_KEY, or managed identity (account name only)
```

Concurrent workers writing to the same partition are safe: each write acquires a 30-second Azure Blob lease, so racing writers queue rather than overwrite each other. Workers writing to different partitions — the common case when parallelising by symbol — are unaffected by locking.

### AWS S3

```bash
# Write to S3
crmd fetch --provider kucoin --symbol BTC-USDT --timeframe 1h \
           --start 2026-01-01 --end 2026-01-08 \
           --output s3://mybucket/crypto-data

# Read from S3
crmd query ohlcv --path s3://mybucket/crypto-data --symbol BTC-USDT
crmd serve       --path s3://mybucket/crypto-data --port 8050
```

Install the S3 extra and set credentials:

```bash
pip install -e ".[s3]"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
# or use IAM roles / AWS_PROFILE
```

### Google Cloud Storage

```bash
# Write to GCS
crmd fetch --provider kucoin --symbol BTC-USDT --timeframe 1h \
           --start 2026-01-01 --end 2026-01-08 \
           --output gs://mybucket/crypto-data

# Read from GCS
crmd query ohlcv --path gs://mybucket/crypto-data --symbol BTC-USDT
crmd serve       --path gs://mybucket/crypto-data --port 8050
```

Install the GCS extra and set credentials:

```bash
pip install -e ".[gcs]"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
# or use gcloud auth application-default login
```

→ [Storage: Write Path](https://bigmikecreates.github.io/crypto-market-data-platform/storage-e2e/) for the full pipeline and concurrency model.

---

## Key design decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Strings for numeric fields** — store `open`, `high`, `low`, `close`, `volume` as `str` in the model layer. | ~68% less memory than Python `Decimal`; avoids parse round-trip when providers return strings anyway; regex validation before conversion. The `decimal128(38,10)` cast is deferred to write time in a single vectorised C++ operation. |
| 2 | **Idempotent fetch** — re-fetching the same date range is safe. | Each row is identified by a merge key (`exchange`, `symbol`, `timeframe`, `source`, `timestamp`). The writer upserts: identical rows are skipped, corrected rows replace old ones, new rows appended. Small partitions use a Python dict merge; larger ones use a DuckDB SQL anti-join. |
| 3 | **Concurrent writes** — multiple workers writing at once are safe. | Local storage workers write to different partition files (one per symbol) and never collide. Cloud storage uses blob leases to serialise writes to the same partition: the second worker waits, reads the merged result, merges its changes, and writes again. No data loss. |
| 4 | **Batch validation** — invalid data never reaches storage. | Before writing, every batch is checked: required fields present, valid decimals, correct timestamp format, OHLC invariants (`high >= open`, `high >= close`), and no duplicate timestamps. If any check fails, the entire batch is rejected — no partial writes. |
| 5 | **ABC for query service** — both `crmd query` and `GET /candles` depend on a `QueryService` interface. | Swap DuckDB for Postgres, InfluxDB, or another engine by writing a new class that implements the interface. CLI and API code never changes.

---

## Python API

For programmatic access, use the `StorageBackend` abstraction to write data:

```python
from crmd_platform.storage import create_backend, write_candles
from crmd_platform.models.candle import Candle

# Create backend explicitly (recommended)
backend = create_backend("s3://mybucket/crypto-data")

# Write candles
candles = [
    Candle(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp="2026-01-01T00:00:00",
        open="42000.0",
        high="42500.0",
        low="41800.0",
        close="42300.0",
        volume="1234.5",
        source="binance",
    )
]

write_candles(candles, backend=backend)
```

**Note:** The `base_path` parameter is deprecated. Use the `backend` parameter with an explicit backend instance for new code. The `base_path` parameter will emit a `DeprecationWarning` and will be removed in a future version.

---

## Development

```bash
pip install -e ".[test,lint,azure]"  # azure is optional; omit if not using Azure Blob

pytest                          # run all tests
ruff check src/ tests/          # lint
ruff format src/ tests/         # format
mypy src/                       # type check

# Benchmark the I/O pipeline (synthetic, CPU-bound)
python scripts/benchmark_pipeline.py run --count 10000 --iterations 10

# Profile a live provider (network-bound)
python scripts/benchmark_pipeline.py profile \
  --start 2026-05-01 --end 2026-05-02

# Docker Compose (production)
docker compose up --build

# Docker Compose (development — hot-reload on source changes)
docker compose -f docker-compose.dev.yml up --build

# Or build and run the backend image manually
docker build -t crmd .
docker run -p 8050:8050 -v ./data:/app/data crmd
```

---

## Documentation

Full documentation: **[bigmikecreates.github.io/crypto-market-data-platform](https://bigmikecreates.github.io/crypto-market-data-platform/)**

| Section | Contents |
|---|---|
| [Getting Started](https://bigmikecreates.github.io/crypto-market-data-platform/getting-started/) | Install, first fetch, live providers, concurrent ingestion, Azure Blob |
| [Architecture](https://bigmikecreates.github.io/crypto-market-data-platform/architecture/) | Write/read path layers, cloud storage, design decisions |
| [Data Model](https://bigmikecreates.github.io/crypto-market-data-platform/data-model/) | `Candle` and `FundingRate` schema; why strings |
| [Validation Strategy](https://bigmikecreates.github.io/crypto-market-data-platform/validation-strategy/) | Rule set, `ValidationResult`, blocking behaviour |
| [Storage: Write Path](https://bigmikecreates.github.io/crypto-market-data-platform/storage-e2e/) | Stage-by-stage write pipeline, Azure variant, concurrency model |
| [Benchmarking](https://bigmikecreates.github.io/crypto-market-data-platform/benchmark-design/) | How the benchmark works, baseline metrics, and provider profiles |

---

## Web Console (frontend)

A Next.js + TypeScript web console lives in `frontend/`. It connects to the FastAPI backend for querying, inspecting, and visualising market data.

```
frontend/
  app/          — pages (explorer, datasets, home)
  components/   — CandlestickChart, CandleTable
  lib/          — Zod schemas, typed API client, TypeScript types
```

### Local dev (no Docker)

```bash
# Terminal 1 — start the backend
crmd serve

# Terminal 2 — start the frontend
cd frontend
cp .env.local.example .env.local   # defaults to http://localhost:8050
npm install
npm run dev
```

Open `http://localhost:3000`. The backend CORS is pre-configured for both `http://localhost:3000` and `http://127.0.0.1:3000`.

### Docker Compose (dev — hot-reload)

```bash
docker compose -f docker-compose.dev.yml up --build
```

Open `http://localhost:3000`. The dev compose file mounts `frontend/` as a volume so Next.js HMR picks up file changes immediately. The backend uses `--reload` and mounts `src/` for the same effect.

### Docker Compose (production)

```bash
docker compose up --build
```

Open `http://localhost:3000`. Both services run in production mode with optimised images, no volume mounts for source.

### Key dependencies

- **Next.js 15** with App Router and server components
- **TanStack Query** for API state management (caching, loading, error states)
- **Zod** for response validation at the API boundary
- **lightweight-charts** for candlestick visualisation
- **Tailwind CSS 3** with `darkMode: "media"` (follows OS preference)

---

## License

All Rights Reserved. See [LICENSE](LICENSE) for details.
