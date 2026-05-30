import pytest

from cmpd.models.funding_rate import FundingRate
from cmpd.validation.funding_rates import (
    validate_funding_rate_batch,
)


def _funding_rate(**overrides) -> FundingRate:
    fields = dict(
        exchange="test_exchange",
        symbol="PI_XBTUSD",
        timestamp="2024-01-01T12:00:00",
        rate="0.0001",
        predicted_rate="0.0002",
        next_funding_time="2024-01-01T16:00:00",
        source="kraken_fake",
    )
    fields.update(overrides)
    return FundingRate(**fields)


# -- happy path ------------------------------------------------


def test_valid_funding_rate_passes():
    result = validate_funding_rate_batch([_funding_rate()])
    assert result.passed
    assert result.issues == []


def test_multiple_valid_rates():
    rates = [
        _funding_rate(
            timestamp="2024-01-01T12:00:00", next_funding_time="2024-01-01T16:00:00"
        ),
        _funding_rate(
            timestamp="2024-01-01T16:00:00", next_funding_time="2024-01-01T20:00:00"
        ),
    ]
    result = validate_funding_rate_batch(rates)
    assert result.passed
    assert len(result.issues) == 0


def test_empty_batch_passes():
    result = validate_funding_rate_batch([])
    assert result.passed
    assert result.issues == []


def test_negative_rate_is_valid():
    r = _funding_rate(rate="-0.0005")
    result = validate_funding_rate_batch([r])
    assert result.passed
    assert result.issues == []


# -- EMPTY_FIELD -----------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "exchange",
        "symbol",
        "timestamp",
        "rate",
        "predicted_rate",
        "next_funding_time",
        "source",
    ],
)
def test_empty_field_yields_EMPTY_FIELD(field: str):
    r = _funding_rate(**{field: ""})
    result = validate_funding_rate_batch([r])
    codes = [i.code for i in result.issues]
    assert "EMPTY_FIELD" in codes
    assert not result.passed


# -- INVALID_DECIMAL -------------------------------------------


@pytest.mark.parametrize(
    "field,bad_val",
    [
        ("rate", "abc"),
        ("predicted_rate", "1.2.3"),
    ],
)
def test_invalid_decimal_string(field: str, bad_val: str):
    r = _funding_rate(**{field: bad_val})
    result = validate_funding_rate_batch([r])
    codes = [i.code for i in result.issues]
    assert "INVALID_DECIMAL" in codes
    assert not result.passed


# -- PRECISION_OVERFLOW ----------------------------------------


def test_precision_overflow_is_warning():
    val = "9" * 39 + ".0"
    r = _funding_rate(rate=val)
    result = validate_funding_rate_batch([r])
    codes = [i.code for i in result.issues]
    assert "PRECISION_OVERFLOW" in codes
    issue = next(i for i in result.issues if i.code == "PRECISION_OVERFLOW")
    assert issue.severity == "warning"


# -- INVALID_TIMESTAMP -----------------------------------------


@pytest.mark.parametrize(
    "bad_ts",
    [
        "not-a-date",
        "2024/01/01T12:00:00",
        "",
    ],
)
def test_invalid_timestamp(bad_ts: str):
    r = _funding_rate(timestamp=bad_ts)
    result = validate_funding_rate_batch([r])
    codes = [i.code for i in result.issues]
    assert "INVALID_TIMESTAMP" in codes
    assert not result.passed


def test_invalid_next_funding_time():
    r = _funding_rate(next_funding_time="not-a-date")
    result = validate_funding_rate_batch([r])
    codes = [i.code for i in result.issues]
    assert "INVALID_TIMESTAMP" in codes
    assert not result.passed


# -- FUNDING_RATE_OUT_OF_RANGE ---------------------------------


@pytest.mark.parametrize(
    "field,val",
    [
        ("rate", "0.006"),
        ("predicted_rate", "-0.006"),
        ("rate", "1.0"),
    ],
)
def test_rate_out_of_range_warning(field: str, val: str):
    r = _funding_rate(**{field: val})
    result = validate_funding_rate_batch([r])
    codes = [i.code for i in result.issues]
    assert "FUNDING_RATE_OUT_OF_RANGE" in codes
    issue = next(i for i in result.issues if i.code == "FUNDING_RATE_OUT_OF_RANGE")
    assert issue.severity == "warning"


# -- FUTURE_BEFORE_CURRENT -------------------------------------


def test_next_funding_time_before_timestamp():
    r = _funding_rate(
        timestamp="2024-01-01T16:00:00",
        next_funding_time="2024-01-01T12:00:00",
    )
    result = validate_funding_rate_batch([r])
    codes = [i.code for i in result.issues]
    assert "FUTURE_BEFORE_CURRENT" in codes
    assert not result.passed


def test_next_funding_time_equal_to_timestamp():
    r = _funding_rate(
        timestamp="2024-01-01T12:00:00",
        next_funding_time="2024-01-01T12:00:00",
    )
    result = validate_funding_rate_batch([r])
    codes = [i.code for i in result.issues]
    assert "FUTURE_BEFORE_CURRENT" in codes
    assert not result.passed


def test_next_funding_time_ordering_ok():
    r = _funding_rate(
        timestamp="2024-01-01T12:00:00",
        next_funding_time="2024-01-01T16:00:00",
    )
    result = validate_funding_rate_batch([r])
    assert result.passed


# -- DUPLICATE_TIMESTAMP ---------------------------------------


def test_duplicate_timestamp_detected():
    rates = [
        _funding_rate(timestamp="2024-01-01T12:00:00"),
        _funding_rate(timestamp="2024-01-01T12:00:00"),
    ]
    result = validate_funding_rate_batch(rates)
    codes = [i.code for i in result.issues]
    assert "DUPLICATE_TIMESTAMP" in codes
    assert not result.passed


def test_same_timestamp_different_exchange_allowed():
    rates = [
        _funding_rate(exchange="exchange_a", timestamp="2024-01-01T12:00:00"),
        _funding_rate(exchange="exchange_b", timestamp="2024-01-01T12:00:00"),
    ]
    result = validate_funding_rate_batch(rates)
    assert result.passed
    assert result.issues == []


def test_same_timestamp_different_symbol_allowed():
    rates = [
        _funding_rate(symbol="PI_XBTUSD", timestamp="2024-01-01T12:00:00"),
        _funding_rate(symbol="PI_ETHUSD", timestamp="2024-01-01T12:00:00"),
    ]
    result = validate_funding_rate_batch(rates)
    assert result.passed
    assert result.issues == []
