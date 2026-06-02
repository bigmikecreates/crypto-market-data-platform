from crmd_platform.models.candle import Candle
from crmd_platform.validation.common import (
    _check_decimals as _common_check_decimals,
    _check_non_empty as _common_check_non_empty,
    check_duplicate_timestamps,
)
from crmd_platform.validation.patterns import (
    UNSIGNED_DECIMAL_PATTERN,
    TIMESTAMP_PATTERN,
    decimal_gte,
)
from crmd_platform.validation.result import (
    ValidationIssue,
    ValidationResult,
)

_DECIMAL_FIELDS = ["open", "high", "low", "close", "volume"]
_ALL_FIELDS = _DECIMAL_FIELDS + [
    "exchange",
    "symbol",
    "timeframe",
    "timestamp",
    "source",
]

_PRECISION_OVERFLOW_SEVERITY = "warning"


_check_non_empty = _common_check_non_empty(_ALL_FIELDS)
_check_decimals = _common_check_decimals(_DECIMAL_FIELDS, _PRECISION_OVERFLOW_SEVERITY)


def _check_non_negative(
    candle: Candle, index: int, issues: list[ValidationIssue]
) -> None:
    for field in _DECIMAL_FIELDS:
        val = getattr(candle, field, "")
        if val.startswith("-"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="NEGATIVE_VALUE",
                    message=f"Field '{field}' is negative: '{val}'.",
                    record_index=index,
                    field=field,
                )
            )


def _check_timestamp(candle: Candle, index: int, issues: list[ValidationIssue]) -> None:
    if not TIMESTAMP_PATTERN.match(candle.timestamp):
        issues.append(
            ValidationIssue(
                severity="error",
                code="INVALID_TIMESTAMP",
                message=f"Timestamp is not a valid ISO-8601 string: '{candle.timestamp}'.",
                record_index=index,
                field="timestamp",
            )
        )


def _check_ohlc_invariants(
    candle: Candle,
    index: int,
    issues: list[ValidationIssue],
) -> None:
    high = getattr(candle, "high", "")
    low = getattr(candle, "low", "")
    open_v = getattr(candle, "open", "")
    close = getattr(candle, "close", "")

    if not all(UNSIGNED_DECIMAL_PATTERN.match(v) for v in [high, low, open_v, close]):
        return

    if not decimal_gte(high, open_v):
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_INVARIANT",
                message=f"'high' ({high}) is less than 'open' ({open_v}).",
                record_index=index,
                field="high",
            )
        )
    if not decimal_gte(high, close):
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_INVARIANT",
                message=f"'high' ({high}) is less than 'close' ({close}).",
                record_index=index,
                field="high",
            )
        )
    if not decimal_gte(open_v, low):
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_INVARIANT",
                message=f"'low' ({low}) exceeds 'open' ({open_v}).",
                record_index=index,
                field="low",
            )
        )
    if not decimal_gte(close, low):
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_INVARIANT",
                message=f"'low' ({low}) exceeds 'close' ({close}).",
                record_index=index,
                field="low",
            )
        )


_CANDLE_DUP_KEY_FIELDS = ["exchange", "symbol", "timeframe", "source", "timestamp"]


def validate_candle_batch(candles: list[Candle]) -> ValidationResult:
    if not candles:
        return ValidationResult(passed=True, issues=[])

    issues: list[ValidationIssue] = []

    for idx, candle in enumerate(candles):
        _check_non_empty(candle, idx, issues)
        _check_decimals(candle, idx, issues)
        _check_non_negative(candle, idx, issues)
        _check_timestamp(candle, idx, issues)
        _check_ohlc_invariants(candle, idx, issues)

    check_duplicate_timestamps(candles, range(len(candles)), issues, _CANDLE_DUP_KEY_FIELDS)

    return ValidationResult(
        passed=not any(issue.severity == "error" for issue in issues),
        issues=issues,
    )
