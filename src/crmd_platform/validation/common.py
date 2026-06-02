from collections.abc import Callable
from typing import Any

from crmd_platform.validation.patterns import SIGNED_DECIMAL_PATTERN, digit_count
from crmd_platform.validation.result import ValidationIssue


def _check_non_empty(
    all_fields: list[str],
) -> Callable[[Any, int, list[ValidationIssue]], None]:
    def check(record: Any, index: int, issues: list[ValidationIssue]) -> None:
        for field in all_fields:
            if not getattr(record, field, "").strip():
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="EMPTY_FIELD",
                        message=f"Field '{field}' is empty.",
                        record_index=index,
                        field=field,
                    )
                )

    return check


def _check_decimals(
    decimal_fields: list[str],
    overflow_severity: str = "warning",
) -> Callable[[Any, int, list[ValidationIssue]], list[str]]:
    def check(record: Any, index: int, issues: list[ValidationIssue]) -> list[str]:
        valid_decimals: list[str] = []
        for field in decimal_fields:
            val = getattr(record, field, "")
            if not SIGNED_DECIMAL_PATTERN.match(val):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="INVALID_DECIMAL",
                        message=f"Field '{field}' is not a valid decimal string: '{val}'.",
                        record_index=index,
                        field=field,
                    )
                )
            else:
                if digit_count(val.replace("-", "")) > 38:
                    issues.append(
                        ValidationIssue(
                            severity=overflow_severity,
                            code="PRECISION_OVERFLOW",
                            message=f"Field '{field}' exceeds 38-digit precision: '{val}'.",
                            record_index=index,
                            field=field,
                        )
                    )
                valid_decimals.append(val)
        return valid_decimals

    return check


def check_duplicate_timestamps(
    records: list[Any],
    valid_indices: range,
    issues: list[ValidationIssue],
    key_fields: list[str],
) -> None:
    seen: set[tuple] = set()
    for idx in valid_indices:
        r = records[idx]
        key = tuple(getattr(r, f) for f in key_fields)
        if key in seen:
            ts = key[-1]
            qualifier = "/".join(str(v) for v in key[:-1])
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DUPLICATE_TIMESTAMP",
                    message=f"Duplicate timestamp '{ts}' for {qualifier}.",
                    record_index=idx,
                    field="timestamp",
                )
            )
        else:
            seen.add(key)
