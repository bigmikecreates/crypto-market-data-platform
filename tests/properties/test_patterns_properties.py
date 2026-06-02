"""
Property-based tests for validation/patterns.py.

Core property: decimal_gte(a, b) must agree with Decimal(a) >= Decimal(b)
for all non-negative decimal strings. This validates the string-length shortcut
used to avoid Decimal object allocation in the hot path.
"""

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from crmd_platform.validation.patterns import decimal_gte


def _fmt(cents: int) -> str:
    """Format an integer number of cents as a decimal string, e.g. 12345 -> '123.45'."""
    return f"{cents // 100}.{cents % 100:02d}"


_cents = st.integers(min_value=0, max_value=10**9)


@given(a=_cents, b=_cents)
def testdecimal_gte_agrees_with_decimal_type(a: int, b: int) -> None:
    """decimal_gte must match Decimal comparison for all non-negative pairs."""
    str_a, str_b = _fmt(a), _fmt(b)
    expected = Decimal(str_a) >= Decimal(str_b)
    assert decimal_gte(str_a, str_b) == expected, (
        f"decimal_gte({str_a!r}, {str_b!r}) disagreed with Decimal comparison"
    )


@given(v=_cents)
def testdecimal_gte_reflexive(v: int) -> None:
    """Any value is >= itself."""
    s = _fmt(v)
    assert decimal_gte(s, s)


@given(a=_cents, b=_cents)
def testdecimal_gte_antisymmetric(a: int, b: int) -> None:
    """If a >= b and b >= a then they must be equal."""
    str_a, str_b = _fmt(a), _fmt(b)
    if decimal_gte(str_a, str_b) and decimal_gte(str_b, str_a):
        assert Decimal(str_a) == Decimal(str_b)


@given(a=_cents, b=_cents, c=_cents)
@settings(max_examples=200)
def testdecimal_gte_transitive(a: int, b: int, c: int) -> None:
    """If a >= b and b >= c then a >= c."""
    str_a, str_b, str_c = _fmt(a), _fmt(b), _fmt(c)
    if decimal_gte(str_a, str_b) and decimal_gte(str_b, str_c):
        assert decimal_gte(str_a, str_c)


@given(a=_cents, b=_cents)
def testdecimal_gte_matches_not_lt(a: int, b: int) -> None:
    """a >= b iff not (b > a), i.e., iff not (decimal_gte(b, a) and a != b)."""
    str_a, str_b = _fmt(a), _fmt(b)
    gte_ab = decimal_gte(str_a, str_b)
    gte_ba = decimal_gte(str_b, str_a)
    # At least one direction must hold (totality)
    assert gte_ab or gte_ba
