# Agent Instructions

## Project Direction

This project is a local-first crypto market-data ingestion platform. Preserve the current architecture:

Provider -> Candle[] -> validation boundary -> Parquet writer -> benchmark/query tooling

Do not turn this into a trading bot, dashboard, or strategy engine.

## Validation Approach

Use layered validation with provider-informed refinement.

Validation should happen at explicit boundaries:

1. Provider boundary: raw provider response -> Candle objects
2. Service boundary: Candle batch -> validated ingestion batch
3. Storage boundary: validated batch -> Parquet table/file
4. Query boundary: stored dataset -> user/API result

Before adding more providers, implement only provider-independent rules:

- decimal parse validation
- timestamp parse validation
- OHLC invariant validation
- duplicate timestamp validation within a batch
- storage row-count/partition validation

Do not overdesign completeness, gap detection, provider scoring, or provider-specific warning systems until real provider behaviour justifies it.

## Provider Selection

Follow the ranking in `docs/benchmarks/provider-selection.md`.
Start with the highest-ranked provider (Bitfinex) to maximise
validation-layer stress from the first integration. Use constrained
providers (Kraken, etc.) later as targeted edge-case tests against
infrastructure already proven at scale.

## Provider Rules

When adding a provider:

- preserve FakeProvider behaviour
- implement the existing OHLCVProvider interface
- document symbol and timeframe mappings
- document timestamp semantics
- add fixture-based tests that do not require live network access
- update validation rules only when provider behaviour justifies them

## Storage Rules

The Parquet writer must preserve partition correctness:

- each output partition must contain only rows belonging to that partition
- row counts must match expected rows for that partition
- writer logic must not induce duplicate rows
- schema must remain explicit and tested

## Testing

Every feature change should include tests.

Prefer focused tests for:

- provider parsing
- validation rules
- partitioned storage writes
- timestamp handling
- decimal conversion

## Drift Evaluation (Pending — not yet implemented)

Drift detection between source code and API reference docs.

Planned approach:
- Manifest generation scripts in Repo A (CLI tree, OpenAPI schema, Python API surface)
- Doc parsing scripts for the Docsify-rendered API reference pages
- LLM evaluation (Azure OpenAI, probable) comparing manifests against doc content
- CI workflow (weekly cron + manual trigger) producing structured drift reports
- Reports archived to a dedicated `reports/` branch
- GitHub Issue creation on drift detection

Not yet started. Implementation deferred to a future iteration.
