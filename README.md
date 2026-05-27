# Crypto Market Data Platform

Local-first cryptocurrency OHLCV market data ingestion. Candles are modelled
as string fields for memory efficiency, converted to `decimal128` Parquet at
write time via C++ `.cast()`. Pluggable providers, Typer CLI, and a staged
benchmark pipeline for performance analysis.

## Architecture

```
User → CLI (typer) → IngestionService → Provider → Candle[]
                                       → ParquetWriter → data/{exchange}/…
                                       → Benchmark (scripts/)
```

## Package Layout

```
src/crypto_market_data_platform/
├── __init__.py
├── config.py              # TimestampConfig
├── models/
│   └── candle.py          # Candle @dataclass(slots=True), all fields str
├── providers/
│   ├── base.py            # MarketDataProvider ABC
│   └── fake.py            # FakeProvider (hardcoded candles)
├── storage/
│   └── parquet_writer.py  # write_candles(), candle_to_table()
├── cli/
│   ├── main.py            # Typer fetch command
│   └── ingestion_service.py
└── benchmark/
    ├── core.py            # PipelineRunner ABC, BenchmarkContext
    ├── rules.py           # CrossValidationRule engine (5 default + 2 verbose)
    └── runners.py         # CandlePipelineRunner (coarse + verbose)

scripts/
└── benchmark_pipeline.py  # Typer CLI for benchmark runs

docs/benchmarks/
└── design-rationale.md    # All design decisions with evidence
```

## Key Concepts

- **Candle** — all fields (`open`, `high`, `low`, `close`, `volume`,
  `timestamp`) stored as `str`. Deferred conversion to `decimal128(38,10)`
  and `timestamp[s|us]` at write time via PyArrow C++ `.cast()`.
- **TimestampConfig** — controls timestamp resolution (`s` default, `us`
  opt-in). Passed through to the writer.
- **Providers** — `MarketDataProvider` ABC. `FakeProvider` built in. Real
  exchange providers are pluggable via the same interface.
- **ParquetWriter** — writes hierarchical paths
  `data/{exchange}/{symbol}/{timeframe}/{date}.parquet`. Uses fixed schema
  `decimal128(38,10)` for all numeric columns regardless of ticker.
- **Benchmark** — staged wall-clock, CPU, memory, GC, and file-size
  measurements with cross-validation rules. Default (shared core) and
  `--isolated` modes. Confidence intervals via t-distribution (N=5 default).

## Quickstart

```bash
# Install
.venv/bin/pip install -e .

# Benchmark the pipeline (1,000 candles)
.venv/bin/python scripts/benchmark_pipeline.py --count 1000

# Benchmark with verbose stage breakdown
.venv/bin/python scripts/benchmark_pipeline.py --count 1000 --verbose

# Fetch fake data via CLI
.venv/bin/python -m crypto_market_data_platform.cli.main fetch --provider fake
```

For detailed design decisions behind each choice, see
[`docs/benchmarks/design-rationale.md`](docs/benchmarks/design-rationale.md).
