from crypto_market_data_platform.models.funding_rate import FundingRate
from crypto_market_data_platform.validation.patterns import (
    _SIGNED_DECIMAL_PATTERN,
    _TIMESTAMP_PATTERN,
    _decimal_gte,
    _digit_count,
)
from crypto_market_data_platform.validation.result import ValidationIssue, ValidationResult

_DECIMAL_FIELDS = ["rate", "predicted_rate"]
_ALL_FIELDS = _DECIMAL_FIELDS + ["exchange", "symbol", "timestamp", "next_funding_time", "source"]

_PRECISION_OVERFLOW_SEVERITY = "warning"
_FUNDING_RATE_CAP = "0.005"


def _check_non_empty(rate: FundingRate, index: int, issues: list[ValidationIssue]) -> None:
    for field in _ALL_FIELDS:
        if not getattr(rate, field, "").strip():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="EMPTY_FIELD",
                    message=f"Field '{field}' is empty.",
                    candle_index=index,
                    field=field,
                )
            )


def _check_decimals(rate: FundingRate, index: int, issues: list[ValidationIssue]) -> list[str]:
    valid_decimals: list[str] = []
    for field in _DECIMAL_FIELDS:
        val = getattr(rate, field, "")
        if not _SIGNED_DECIMAL_PATTERN.match(val):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_DECIMAL",
                    message=f"Field '{field}' is not a valid decimal string: '{val}'.",
                    candle_index=index,
                    field=field,
                )
            )
        else:
            digit_count = _digit_count(val.replace("-", ""))
            if digit_count > 38:
                issues.append(
                    ValidationIssue(
                        severity=_PRECISION_OVERFLOW_SEVERITY,
                        code="PRECISION_OVERFLOW",
                        message=f"Field '{field}' exceeds 38-digit precision: '{val}'.",
                        candle_index=index,
                        field=field,
                    )
                )
            valid_decimals.append(val)
    return valid_decimals


def _check_rate_range(rate: FundingRate, index: int, issues: list[ValidationIssue]) -> None:
    for field in _DECIMAL_FIELDS:
        val = getattr(rate, field, "")
        if not _SIGNED_DECIMAL_PATTERN.match(val):
            continue
        abs_val = val.lstrip("-")
        if abs_val and _decimal_gte(abs_val, _FUNDING_RATE_CAP):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="FUNDING_RATE_OUT_OF_RANGE",
                    message=f"Field '{field}' ({val}) exceeds typical ±0.5% range.",
                    candle_index=index,
                    field=field,
                )
            )


def _check_timestamps(rate: FundingRate, index: int, issues: list[ValidationIssue]) -> None:
    for field in ["timestamp", "next_funding_time"]:
        val = getattr(rate, field, "")
        if not _TIMESTAMP_PATTERN.match(val):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_TIMESTAMP",
                    message=f"Field '{field}' is not a valid ISO-8601 string: '{val}'.",
                    candle_index=index,
                    field=field,
                )
            )


def _check_timestamp_ordering(rate: FundingRate, index: int, issues: list[ValidationIssue]) -> None:
    ts = rate.timestamp
    nft = rate.next_funding_time
    if _TIMESTAMP_PATTERN.match(ts) and _TIMESTAMP_PATTERN.match(nft):
        if ts >= nft:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="FUTURE_BEFORE_CURRENT",
                    message=f"next_funding_time ({nft}) is not after timestamp ({ts}).",
                    candle_index=index,
                    field="next_funding_time",
                )
            )


def _check_duplicate_timestamps(
    rates: list[FundingRate],
    valid_indices: range,
    issues: list[ValidationIssue],
) -> None:
    seen: set[tuple[str, str, str, str]] = set()
    for idx in valid_indices:
        r = rates[idx]
        key = (r.exchange, r.symbol, r.source, r.timestamp)
        if key in seen:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DUPLICATE_TIMESTAMP",
                    message=f"Duplicate timestamp '{r.timestamp}' for {r.exchange}/{r.symbol}/{r.source}.",
                    candle_index=idx,
                    field="timestamp",
                )
            )
        else:
            seen.add(key)


def validate_funding_rate_batch(rates: list[FundingRate]) -> ValidationResult:
    if not rates:
        return ValidationResult(passed=True, issues=[])

    issues: list[ValidationIssue] = []

    for idx, rate in enumerate(rates):
        _check_non_empty(rate, idx, issues)
        valid_decimals = _check_decimals(rate, idx, issues)
        _check_rate_range(rate, idx, issues)
        _check_timestamps(rate, idx, issues)
        _check_timestamp_ordering(rate, idx, issues)

    _check_duplicate_timestamps(rates, range(len(rates)), issues)

    return ValidationResult(passed=len(issues) == 0, issues=issues)
