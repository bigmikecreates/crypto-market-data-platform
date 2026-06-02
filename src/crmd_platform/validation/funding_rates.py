from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.validation.common import (
    _check_decimals as _common_check_decimals,
    _check_non_empty as _common_check_non_empty,
    check_duplicate_timestamps,
)
from crmd_platform.validation.patterns import (
    SIGNED_DECIMAL_PATTERN,
    TIMESTAMP_PATTERN,
    decimal_gte,
)
from crmd_platform.validation.result import (
    ValidationIssue,
    ValidationResult,
)

_DECIMAL_FIELDS = ["rate", "predicted_rate"]
_ALL_FIELDS = _DECIMAL_FIELDS + [
    "exchange",
    "symbol",
    "timestamp",
    "next_funding_time",
    "source",
]

_PRECISION_OVERFLOW_SEVERITY = "warning"
_FUNDING_RATE_CAP = "0.005"


_check_non_empty = _common_check_non_empty(_ALL_FIELDS)
_check_decimals = _common_check_decimals(_DECIMAL_FIELDS, _PRECISION_OVERFLOW_SEVERITY)


def _check_rate_range(
    rate: FundingRate, index: int, issues: list[ValidationIssue]
) -> None:
    for field in _DECIMAL_FIELDS:
        val = getattr(rate, field, "")
        if not SIGNED_DECIMAL_PATTERN.match(val):
            continue
        abs_val = val.lstrip("-")
        if abs_val and decimal_gte(abs_val, _FUNDING_RATE_CAP):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="FUNDING_RATE_OUT_OF_RANGE",
                    message=f"Field '{field}' ({val}) exceeds typical ±0.5% range.",
                    record_index=index,
                    field=field,
                )
            )


def _check_timestamps(
    rate: FundingRate, index: int, issues: list[ValidationIssue]
) -> None:
    for field in ["timestamp", "next_funding_time"]:
        val = getattr(rate, field, "")
        if not TIMESTAMP_PATTERN.match(val):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_TIMESTAMP",
                    message=f"Field '{field}' is not a valid ISO-8601 string: '{val}'.",
                    record_index=index,
                    field=field,
                )
            )


def _check_timestamp_ordering(
    rate: FundingRate, index: int, issues: list[ValidationIssue]
) -> None:
    ts = rate.timestamp
    nft = rate.next_funding_time
    if TIMESTAMP_PATTERN.match(ts) and TIMESTAMP_PATTERN.match(nft):
        if ts >= nft:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="FUTURE_BEFORE_CURRENT",
                    message=f"next_funding_time ({nft}) is not after timestamp ({ts}).",
                    record_index=index,
                    field="next_funding_time",
                )
            )


_FUNDING_DUP_KEY_FIELDS = ["exchange", "symbol", "source", "timestamp"]


def validate_funding_rate_batch(rates: list[FundingRate]) -> ValidationResult:
    if not rates:
        return ValidationResult(passed=True, issues=[])

    issues: list[ValidationIssue] = []

    for idx, rate in enumerate(rates):
        _check_non_empty(rate, idx, issues)
        _check_decimals(rate, idx, issues)
        _check_rate_range(rate, idx, issues)
        _check_timestamps(rate, idx, issues)
        _check_timestamp_ordering(rate, idx, issues)

    check_duplicate_timestamps(rates, range(len(rates)), issues, _FUNDING_DUP_KEY_FIELDS)

    return ValidationResult(
        passed=not any(issue.severity == "error" for issue in issues),
        issues=issues,
    )
