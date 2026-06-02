# Validation Strategy

The validation layer runs after provider ingestion and before any write to storage. It operates on batches of `Candle` or `FundingRate` records using string values — no `Decimal` objects are created during validation.

## Validation boundaries

The pipeline enforces validation at four explicit boundaries, each with a defined responsibility:

| Boundary | Input → Output | Responsibility |
|---|---|---|
| **Provider** | Raw API response → `list[Candle]` | Field mapping, pagination, string assignment |
| **Service** | `list[Candle]` → `ValidationResult` | Batch-level rule evaluation; blocks write on failure |
| **Storage** | Validated batch → Parquet file | Schema casting, partition routing, row-level upsert |
| **Query** | Parquet files → result rows | `read_parquet` execution, schema normalisation |

Validation logic resides exclusively at the Service boundary. The provider boundary produces well-shaped records; the storage boundary trusts that the service has already validated them.

## Current rule set

Seven provider-independent rules are applied to every `Candle` batch by `validate_candle_batch()`:

| Rule code | Field(s) | What it checks |
|---|---|---|
| `EMPTY_FIELD` | All required fields | No field is `None` or an empty string |
| `INVALID_DECIMAL` | `open`, `high`, `low`, `close`, `volume` | Matches the signed decimal regex — no non-numeric characters |
| `NEGATIVE_VALUE` | `open`, `high`, `low`, `close`, `volume` | No negative values (checks `startswith('-')`) |
| `PRECISION_OVERFLOW` | `open`, `high`, `low`, `close`, `volume` | No more than 38 significant digits (warning severity) |
| `INVALID_TIMESTAMP` | `timestamp` | Matches subset of ISO-8601 (`YYYY-MM-DDTHH:MM:SS` or microsecond precision) |
| `OHLC_INVARIANT` | `open`, `high`, `low`, `close` | `high >= open`, `high >= close`, `low <= open`, `low <= close` |
| `DUPLICATE_TIMESTAMP` | merge key | No two records in the batch share `(exchange, symbol, timeframe, source, timestamp)` |

For funding rate batches, `validate_funding_rate_batch()` applies equivalent rules over the `FundingRate` field set.

## ValidationResult

`validate_candle_batch()` returns a `ValidationResult`:

```python
@dataclass
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue]
```

Each `ValidationIssue` records the candle index, rule code, affected field, and a human-readable message. The full batch is evaluated before returning — no early exit — so all issues in a batch are visible in a single call.

## Blocking behaviour

If `ValidationResult.passed` is `False`, the service raises `ValueError` and the writer is not called. No partial writes occur: the Parquet file is either untouched (existing partition) or not created (new partition).

Advisory validation — logging issues and writing anyway — would silently populate storage with records that violate domain invariants. Downstream queries would then operate on data the pipeline itself flagged as invalid, making the source of errors difficult to trace.

## Decimal string comparison

OHLC invariant checks compare decimal strings without constructing `Decimal` objects. `decimal_gte(a, b)` operates directly on two unsigned decimal strings:

1. Compare integer-part lengths (a longer sequence of digits is always numerically larger for non-negative values with no leading zeros)
2. If equal length, compare integer parts lexicographically
3. Zero-pad fractional parts to equal length, then compare lexicographically

This is consistent with the strings-first data model: values remain strings from provider ingestion through validation with no intermediate Python object allocation.

## Design decisions

**Why provider-independent rules only?**
Completeness rules (expected candle count), gap detection, and timestamp alignment depend on provider-specific pagination behaviour. Adding them before a real provider exposes that behaviour produces rules tuned to synthetic data that break on real API responses. The seven current rules hold for any valid OHLC record, regardless of provider.

**Why four OHLC invariant checks, not seven?**
The seven standard OHLC invariants include `high >= low` and all fields `>= 0`. The rule set implements four: `high >= open`, `high >= close`, `low <= open`, `low <= close`. `high >= low` is entailed by these four via transitivity and is therefore never an independent failure. Non-negativity is enforced by `NEGATIVE_VALUE`, which checks for values < 0. Implementing entailed checks would never catch a case the primary four missed.

**Why full-batch evaluation?**
A paginated batch may contain multiple independent issues across different candles and fields. Failing on the first and requiring a retry reveals one issue per attempt. Full-batch evaluation returns all issues simultaneously, so a single call can identify, for example, that all 50 `INVALID_DECIMAL` failures are on `volume` because the provider is returning `"1,234"` instead of `"1234"`.

## Provider-informed refinement

The current rule set is the starting point. Rules are added after observing real provider behaviour. Candidates identified from provider integrations completed so far:

- Timestamp alignment to timeframe boundaries (some providers return candle-open time, others candle-close time)
- Completeness validation against the expected candle count for a time range and timeframe
- Zero-volume candle handling (some providers omit them; others include them with `volume = "0"`)

See [Validation Rules Reference](/crypto-market-data-platform/reference/#/validation-rules) for rule codes, severity levels, and descriptions.
