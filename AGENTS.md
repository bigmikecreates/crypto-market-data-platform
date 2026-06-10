# Agent Instructions

## Project Direction

This project is a crypto market-data ingestion platform supporting both local and cloud deployments. Preserve the current architecture:

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

## Implement-Validate-Report Cycle

After completing any significant implementation, the agent must:

1. **Re-review what was done** — re-read the requirements/user intent, the changed files, and confirm no scope drift or missed details
2. **Run validation** — execute relevant existing tests, run a manual smoke test (e.g. CLI command or Python snippet that exercises the new code), and confirm the output is correct
3. **Debug failures** — if tests fail or the smoke test produces wrong results, diagnose the root cause, fix the code, and run validation again
4. **Report results** — summarise what was built, what was validated, and (if applicable) what was fixed after the first validation attempt
5. **Await approval** — do not proceed to subsequent items on the itinerary until the user explicitly approves the completed work

## Drift Evaluation (Pending — tracked in issue #17)

Drift detection between source code and API reference docs.

Planned approach:
- Manifest generation scripts in Repo A (CLI tree, OpenAPI schema, Python API surface)
- Doc parsing scripts for the Docsify-rendered API reference pages
- LLM evaluation (Azure OpenAI, probable) comparing manifests against doc content
- CI workflow (weekly cron + manual trigger) producing structured drift reports
- Reports archived to a dedicated `reports/` branch
- GitHub Issue creation on drift detection

Not yet started. Tracked in issue [#17](https://github.com/bigmikecreates/crypto-market-data-platform/issues/17).

## graphify

This project has a knowledge graph at graphify-out/ with 1954 nodes and 5267 edges across 173 communities.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
