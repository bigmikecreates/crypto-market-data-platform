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

## Current Validation State

The current `Candle` model is a lightweight `@dataclass(slots=True)` where all fields are strings:

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

The fake provider currently returns one hardcoded candle using string numeric fields and `timestamp=start.isoformat()`.

The Parquet writer currently performs storage-bound validation:

- numeric fields are checked against a decimal-string regex
- numeric fields are cast to `decimal128(38, 10)`
- timestamp strings are cast to the configured Arrow timestamp type

This means the current validation approach is mostly:

- structural shape via the `Candle` dataclass
- parse/cast validation at Parquet write time
- no explicit domain-level market-data validation yet

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

Question:

```text
Can values be parsed into the types required by storage and analysis?
```

Rules:

- `open`, `high`, `low`, `close`, and `volume` must be decimal-compatible strings
- `timestamp` must be parseable/castable into the configured timestamp type
- `exchange`, `symbol`, `timeframe`, and `source` must be non-empty strings

This validation can initially reuse the same assumptions currently enforced by the Parquet writer, but should eventually move into a dedicated validation module.

### 3. Market-Data Domain Invariant Validation

Question:

```text
Does the candle make sense as OHLCV market data?
```

Provider-independent rules:

- open >= 0
- high >= 0
- low >= 0
- close >= 0
- volume >= 0
- high >= open
- high >= close
- high >= low
- low <= open
- low <= close
- low <= high

These rules are safe to implement early because they are intrinsic to OHLCV data.

### 4. Time-Series Validation

Question:

```text
Does the candle batch make sense as timestamped data?
```

Initial rules:

- timestamps should be sortable
- timestamps should not duplicate within the same `exchange/symbol/timeframe/source` batch
- timestamps should fall within the requested start/end range where applicable

Provider-informed rules to add later:

- timestamp alignment to timeframe boundaries
- open-time vs close-time semantics
- start/end inclusive or exclusive behaviour
- whether the latest partial candle is included

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

Question:

```text
Does each provider adapter obey the project's provider contract?
```

Each provider should prove that it:

- returns `list[Candle]`
- uses the canonical `Candle` schema
- returns timestamps in a documented format
- documents timestamp semantics
- handles unsupported symbols/timeframes clearly
- does not silently return malformed data
- preserves fake provider behaviour while adding real providers

Provider contract tests should use fixtures where possible so tests do not require live network access.

### 7. Storage Validation

Question:

```text
Did the validated records land correctly in storage?
```

Rules:

- written paths match candle dates
- each partition contains only rows belonging to that partition
- written row count matches expected row count for that partition
- Parquet schema matches the expected schema
- numeric columns are `decimal128(38, 10)`
- timestamp column respects `TimestampConfig`
- writer logic does not induce duplicate rows

This layer is important because storage bugs can be misdiagnosed as provider bugs. For example, if the writer duplicates rows, later validation may incorrectly suggest that the provider returned duplicate candles.

## Recommended Data Structures

Validation should return structured issues rather than immediately throwing exceptions for every case.

```python
from dataclasses import dataclass


@dataclass(slots=True)
class ValidationIssue:
    severity: str       # "error" | "warning"
    code: str           # e.g. "INVALID_DECIMAL", "OHLC_INVARIANT", "DUPLICATE_TIMESTAMP"
    message: str
    candle_index: int | None = None
    field: str | None = None


@dataclass(slots=True)
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue]
```

This allows callers to decide whether to fail fast, log warnings, emit reports, or continue.

## Recommended Pipeline

```text
Provider.fetch_ohlcv()
    -> list[Candle]
    -> validate_candle_batch()
    -> write_candles()
    -> verify_written_dataset()
    -> IngestionReport
```

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
