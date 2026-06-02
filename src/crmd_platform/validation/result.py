from dataclasses import dataclass


@dataclass(slots=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    record_index: int | None = None
    field: str | None = None


@dataclass(slots=True)
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue]
