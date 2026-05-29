# Validation Rules Reference

## Candle validation rules

```python
def validate_candle_batch(candles: list[Candle]) -> ValidationResult: ...
```

| Code | Severity | Check | Fields | Example violation |
|------|----------|-------|--------|-------------------|
| `EMPTY_FIELD` | error | Required fields must not be empty | All fields | `open=""` |
| `INVALID_DECIMAL` | error | Numeric fields match signed decimal regex (`^-?[0-9]+(\.[0-9]+)?$`) | `open`, `high`, `low`, `close`, `volume` | `open="abc"`, `high="12,34"` |
| `NEGATIVE_VALUE` | error | Numeric fields must be ≥ 0 | `open`, `high`, `low`, `close`, `volume` | `volume="-5"` |
| `PRECISION_OVERFLOW` | warning | No more than 38 significant digits | `open`, `high`, `low`, `close`, `volume` | `open="1234567890123456789012345678901234567890"` (40 digits) |
| `INVALID_TIMESTAMP` | error | Timestamp matches ISO-8601 pattern (`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$`) | `timestamp` | `timestamp="yesterday"` |
| `OHLC_INVARIANT` | error | `high ≥ open`, `high ≥ close`, `low ≤ open`, `low ≤ close` | `open`, `high`, `low`, `close` | `high="50"`, `open="100"` (high < open) |
| `DUPLICATE_TIMESTAMP` | error | No duplicate `(exchange, symbol, timeframe, source, timestamp)` within batch | All key cols | Two candles with same exchange/symbol/timeframe/source/timestamp |

## Funding rate validation rules

```python
def validate_funding_rate_batch(rates: list[FundingRate]) -> ValidationResult: ...
```

| Code | Severity | Check | Fields | Example violation |
|------|----------|-------|--------|-------------------|
| `EMPTY_FIELD` | error | Required fields must not be empty | All fields | `rate=""` |
| `INVALID_DECIMAL` | error | Numeric fields match signed decimal regex | `rate`, `predicted_rate` | `rate="NaN"` |
| `PRECISION_OVERFLOW` | warning | No more than 38 significant digits | `rate`, `predicted_rate` | `rate` with 40 digits |
| `FUNDING_RATE_OUT_OF_RANGE` | warning | Rate and predicted rate do not exceed ±0.5% | `rate`, `predicted_rate` | `rate="0.01"` (1% > 0.5%) |
| `INVALID_TIMESTAMP` | error | Timestamps match ISO-8601 pattern | `timestamp`, `next_funding_time` | `next_funding_time="never"` |
| `FUTURE_BEFORE_CURRENT` | error | `next_funding_time` must be after `timestamp` | `timestamp`, `next_funding_time` | `next_funding_time` < `timestamp` |
| `DUPLICATE_TIMESTAMP` | error | No duplicate `(exchange, symbol, source, timestamp)` within batch | All key cols | Two rates with same exchange/symbol/source/timestamp |

## Data structures

### ValidationIssue

| Field | Type | Description |
|-------|------|-------------|
| `severity` | `str` | `"error"` or `"warning"` |
| `code` | `str` | Machine-readable rule code (e.g. `"INVALID_DECIMAL"`) |
| `message` | `str` | Human-readable description of the issue |
| `candle_index` | `int \| None` | Index of the failing record within the batch |
| `field` | `str \| None` | Name of the field that failed validation |

### ValidationResult

| Field | Type | Description |
|-------|------|-------------|
| `passed` | `bool` | `True` if there are zero `error`-severity issues |
| `issues` | `list[ValidationIssue]` | All issues found (non-fail-fast collection) |

### Comparison helpers

```python
def _decimal_gte(a: str, b: str) -> bool:
    """String-based decimal comparison: returns True if a >= b.
    Compares integer parts with length-aware padding, zero-pads fractional
    parts. No Decimal objects created."""

def _digit_count(s: str) -> int:
    """Counts significant digits in a decimal string (excludes '.')."""
```

### Regex patterns

```python
_SIGNED_DECIMAL_PATTERN = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
_UNSIGNED_DECIMAL_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)?$")
_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$")
```
