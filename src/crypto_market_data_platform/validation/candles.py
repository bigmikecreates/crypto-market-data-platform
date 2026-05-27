from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.validation.patterns import (
    _SIGNED_DECIMAL_PATTERN,
    _UNSIGNED_DECIMAL_PATTERN,
    _TIMESTAMP_PATTERN,
    _decimal_gte,
    _digit_count,
)
from crypto_market_data_platform.validation.result import ValidationIssue, ValidationResult

_DECIMAL_FIELDS = ["open", "high", "low", "close", "volume"]
_ALL_FIELDS = _DECIMAL_FIELDS + ["exchange", "symbol", "timeframe", "timestamp", "source"]

_PRECISION_OVERFLOW_SEVERITY = "warning"


def _check_non_empty(candle: Candle, index: int, issues: list[ValidationIssue]) -> None:
    for field in _ALL_FIELDS:
        if not getattr(candle, field, "").strip():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="EMPTY_FIELD",
                    message=f"Field '{field}' is empty.",
                    candle_index=index,
                    field=field,
                )
            )


def _check_decimals(candle: Candle, index: int, issues: list[ValidationIssue]) -> list[str]:
    valid_decimals: list[str] = []
    for field in _DECIMAL_FIELDS:
        val = getattr(candle, field, "")
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
            if _digit_count(val.replace("-", "")) > 38:
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


def _check_non_negative(candle: Candle, index: int, issues: list[ValidationIssue]) -> None:
    for field in _DECIMAL_FIELDS:
        val = getattr(candle, field, "")
        if val.startswith("-"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="NEGATIVE_VALUE",
                    message=f"Field '{field}' is negative: '{val}'.",
                    candle_index=index,
                    field=field,
                )
            )


def _check_timestamp(candle: Candle, index: int, issues: list[ValidationIssue]) -> None:
    if not _TIMESTAMP_PATTERN.match(candle.timestamp):
        issues.append(
            ValidationIssue(
                severity="error",
                code="INVALID_TIMESTAMP",
                message=f"Timestamp is not a valid ISO-8601 string: '{candle.timestamp}'.",
                candle_index=index,
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

    if not all(_UNSIGNED_DECIMAL_PATTERN.match(v) for v in [high, low, open_v, close]):
        return

    if not _decimal_gte(high, open_v):
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_INVARIANT",
                message=f"'high' ({high}) is less than 'open' ({open_v}).",
                candle_index=index,
                field="high",
            )
        )
    if not _decimal_gte(high, close):
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_INVARIANT",
                message=f"'high' ({high}) is less than 'close' ({close}).",
                candle_index=index,
                field="high",
            )
        )
    if not _decimal_gte(open_v, low):
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_INVARIANT",
                message=f"'low' ({low}) exceeds 'open' ({open_v}).",
                candle_index=index,
                field="low",
            )
        )
    if not _decimal_gte(close, low):
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_INVARIANT",
                message=f"'low' ({low}) exceeds 'close' ({close}).",
                candle_index=index,
                field="low",
            )
        )


def _check_duplicate_timestamps(
    candles: list[Candle],
    valid_indices: range,
    issues: list[ValidationIssue],
) -> None:
    seen: set[tuple[str, str, str, str, str]] = set()
    for idx in valid_indices:
        c = candles[idx]
        key = (c.exchange, c.symbol, c.timeframe, c.source, c.timestamp)
        if key in seen:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DUPLICATE_TIMESTAMP",
                    message=f"Duplicate timestamp '{c.timestamp}' for {c.exchange}/{c.symbol}/{c.timeframe}/{c.source}.",
                    candle_index=idx,
                    field="timestamp",
                )
            )
        else:
            seen.add(key)


def validate_candle_batch(candles: list[Candle]) -> ValidationResult:
    if not candles:
        return ValidationResult(passed=True, issues=[])

    issues: list[ValidationIssue] = []

    for idx, candle in enumerate(candles):
        _check_non_empty(candle, idx, issues)
        valid_decimals = _check_decimals(candle, idx, issues)
        _check_non_negative(candle, idx, issues)
        _check_timestamp(candle, idx, issues)
        _check_ohlc_invariants(candle, idx, issues)

    _check_duplicate_timestamps(candles, range(len(candles)), issues)

    return ValidationResult(passed=len(issues) == 0, issues=issues)
