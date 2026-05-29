# Validation Strategy

## Purpose

This document defines the validation approach for the crypto market data platform.

The goal is to introduce a validation layer without overdesigning provider-specific rules before real API providers expose their actual behaviour.

The project should use a general methodology that is relevant to:

- market data
- timestamped/time-series data
- provider integration
- storage correctness

The validation strategy should be refined iteratively as each real provider is added.

## Core Principle

Use layered validation with provider-informed refinement.

The stable methodology is:

```text
Validate at explicit system boundaries.
```

Validation should not be scattered randomly through providers, storage writers, CLI handlers, or benchmark code. The project should use clear validation gates.

## Validation Boundaries

### 1. Provider Boundary

```text
raw provider response -> Candle objects
```

This boundary checks whether provider-specific responses can be transformed into the canonical internal candle shape.

Examples:

- Kraken OHLC response -> `Candle`
- FakeProvider hardcoded candle -> `Candle`
- future Coinbase/OKX response -> `Candle`

### 2. Service Boundary

```text
Candle batch -> validated ingestion batch
```

This is where batch-level validation should happen.

Examples:

- decimal parse validation
- timestamp parse validation
- OHLC invariant validation
- duplicate timestamp validation
- requested range validation

### 3. Storage Boundary

```text
validated batch -> Parquet table/file
```

This boundary checks that validated candles are written correctly.

Examples:

- partition correctness
- row-count correctness
- schema correctness
- decimal128 conversion
- timestamp resolution correctness

### 4. Query Boundary

```text
stored dataset -> user/API/query result
```

This boundary checks that stored data can be queried and returned safely.

Examples:

- DuckDB query validation
- date-range filtering
- result schema validation
- empty result handling

## Validation Layers

### 1. Shape Validation

Question:

```text
Does each record have the required Candle fields?
```

Required fields:

- exchange
- symbol
- timeframe
- timestamp
- open
- high
- low
- close
- volume
- source

This is currently mostly handled by the `Candle` dataclass constructor, but because all fields are strings, this only confirms shape, not semantic validity.

### 2. Type / Parse Validation

Question: *Can values be parsed into the types required by storage and analysis?*

→ See [Validation Rules Reference](reference/validation-rules.md) for the
exact rule codes (`INVALID_DECIMAL`, `INVALID_TIMESTAMP`, etc.).

### 3. Market-Data Domain Invariant Validation

Question: *Does the candle make sense as OHLCV market data?*

→ See [Validation Rules Reference](reference/validation-rules.md) for the
exact OHLC invariant checks (`high >= open`, `low <= close`, etc.).

### 4. Time-Series Validation

Question: *Does the candle batch make sense as timestamped data?*

Initial rules: timestamps should be sortable, not duplicate within a batch,
and fall within the requested range where applicable.

Provider-informed rules to add later: timestamp alignment to timeframe
boundaries, open-time vs close-time semantics, and partial candle behaviour.

### 5. Completeness Validation

Question:

```text
Did we receive all expected candles?
```

This should not be fully implemented before real providers.

Completeness validation depends on provider behaviour, including:

- pagination behaviour
- sparse market behaviour
- provider result caps
- whether zero-volume candles are omitted
- whether current/incomplete candles are included
- whether timestamps represent candle-open or candle-close time

Completeness validation should be added after Kraken or another real provider clarifies these behaviours.

### 6. Provider Contract Validation

Question: *Does each provider adapter obey the project's provider contract?*

Each provider should prove that it returns `list[Candle]`, uses the canonical
schema, documents timestamp semantics, and handles unsupported symbols/timeframes
without silently returning malformed data. Tests should use fixtures where
possible to avoid requiring live network access.

### 7. Storage Validation

Question: *Did the validated records land correctly in storage?*

→ See [Validation Rules Reference](reference/validation-rules.md) for the
exact storage validation rules (partition correctness, schema correctness,
row-count checking, duplicate detection).

## Sequencing

### Before Kraken

Implement the validation framework and only obvious provider-independent rules:

- decimal parse validation
- timestamp parse validation
- OHLC invariant validation
- duplicate timestamp validation within a batch
- storage row-count/partition validation

Do not overbuild completeness validation, provider scoring, gap classification, or provider-specific warnings yet.

### During Kraken Integration

Use real Kraken behaviour to refine validation.

Document:

- Kraken timestamp semantics
- Kraken symbol mappings
- Kraken timeframe mappings
- empty response behaviour
- unsupported symbol/timeframe behaviour
- partial latest candle behaviour, if observed
- pagination/result limit behaviour

### After Kraken

Add stronger provider-informed validation:

- expected candle count validation
- missing interval detection
- pagination-aware validation
- checkpoint/retry consistency checks
- provider-specific warnings where justified

## Important Principle

The project should have a general validation methodology early, but not a rigid validation regime based only on fake data.

The goal is:

```text
layered validation + provider-informed refinement
```

This avoids both failure modes:

1. no validation strategy until providers expose bugs
2. overengineering a speculative validation system before real provider behaviour is observed
