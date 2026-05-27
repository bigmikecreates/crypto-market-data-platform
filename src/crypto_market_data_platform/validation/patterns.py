import re

_SIGNED_DECIMAL_PATTERN = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
_UNSIGNED_DECIMAL_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)?$")
_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$")


def _decimal_gte(a: str, b: str) -> bool:
    if a == b:
        return True
    int_a, _, frac_a = a.partition(".")
    int_b, _, frac_b = b.partition(".")
    int_a = int_a.lstrip("0") or "0"
    int_b = int_b.lstrip("0") or "0"
    if len(int_a) != len(int_b):
        return len(int_a) > len(int_b)
    if int_a != int_b:
        return int_a > int_b
    max_len = max(len(frac_a), len(frac_b))
    return frac_a.ljust(max_len, "0") >= frac_b.ljust(max_len, "0")


def _digit_count(s: str) -> int:
    return len(s) - s.count(".")
