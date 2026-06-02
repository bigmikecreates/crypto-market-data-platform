# API Reference

This section documents every interface for interacting with the platform — CLI commands, HTTP endpoints, Python classes, the storage schema, and validation rules.

## CLI Reference

The `crmd` command-line tool. Every subcommand: `fetch`, `datasets`, `inspect`, `serve`, and `query`. Each includes usage signature, all options with types and defaults, merge strategy details, and success/error examples.

**When to reach for it:** You're at a terminal, need to ingest or query data, and want the exact flags, merge strategy behaviour, or error output.

→ [CLI Reference](cli.md)

## HTTP API Reference

REST endpoints for querying stored data: `/health`, `/datasets`, `/candles`, `/funding-rates`, `/summary`, and `POST /query`. Each includes curl usage, parameter tables, and success/error responses.

**When to reach for it:** You're integrating with an external tool over HTTP, or prefer `curl` over the CLI.

→ [HTTP API Reference](http-api.md)

## Python API Reference

Full package surface area: providers (Bitfinex, KuCoin, Bybit, MEXC, Bitstamp, FakeProvider), data models, validation, storage writers, ingestion services, query service, server factory, and benchmark runners. Each function includes import path, constructor signature, parameter tables, and code examples.

**When to reach for it:** You're embedding the pipeline in a Python script — custom ingestion, a new provider adapter, or benchmark runs.

→ [Python API Reference](python-api.md)

## Parquet Schema Reference

On-disk column layout for candle and funding rate tables: Parquet type per column, `decimal128(38,10)` details, timestamp resolution config, and the `exchange/symbol/timeframe/date` partition hierarchy.

**When to reach for it:** You're querying Parquet files directly with DuckDB, debugging schema mismatches, or building external tooling that reads stored files.

→ [Parquet Schema Reference](parquet-schema.md)

## Validation Rules Reference

Catalogue of every rule enforced by `validate_candle_batch()` and `validate_funding_rate_batch()`: rule codes, severity levels, affected fields, and example violations. Includes the `ValidationIssue` / `ValidationResult` data structures and comparison helper signatures.

**When to reach for it:** A validation error blocked your ingestion and you need the rule code, severity, and fix — or you're reviewing what data quality guarantees the pipeline enforces.

→ [Validation Rules Reference](validation-rules.md)
