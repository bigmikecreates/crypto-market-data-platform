import pytest

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.validation.candles import (
    _decimal_gte,
    _digit_count,
    _DECIMAL_PATTERN,
    validate_candle_batch,
)


def _candle(**overrides) -> Candle:
    fields = dict(
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp="2024-01-01T12:00:00",
        open="50000.0",
        high="51000.0",
        low="49500.0",
        close="50500.0",
        volume="100.5",
        source="fake_provider",
    )
    fields.update(overrides)
    return Candle(**fields)


# -- happy path ------------------------------------------------

def test_valid_candle_passes():
    result = validate_candle_batch([_candle()])
    assert result.passed
    assert result.issues == []


def test_multiple_valid_candles():
    candles = [
        _candle(timestamp="2024-01-01T12:00:00"),
        _candle(timestamp="2024-01-01T13:00:00"),
        _candle(timestamp="2024-01-01T14:00:00"),
    ]
    result = validate_candle_batch(candles)
    assert result.passed
    assert len(result.issues) == 0


def test_valid_candle_with_microseconds():
    c = _candle(timestamp="2024-01-01T12:00:00.123456")
    result = validate_candle_batch([c])
    assert result.passed
    assert result.issues == []


def test_empty_batch_passes():
    result = validate_candle_batch([])
    assert result.passed
    assert result.issues == []


# -- EMPTY_FIELD per field -------------------------------------

@pytest.mark.parametrize("field", [
    "exchange", "symbol", "timeframe", "timestamp",
    "open", "high", "low", "close", "volume", "source",
])
def test_empty_field_yields_EMPTY_FIELD(field: str):
    c = _candle(**{field: ""})
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "EMPTY_FIELD" in codes
    assert not result.passed


# -- INVALID_DECIMAL -------------------------------------------

@pytest.mark.parametrize("field,bad_val", [
    ("open", "abc"),
    ("high", "1.2.3"),
    ("low", "12,5"),
    ("close", "0x10"),
    ("volume", ""),
])
def test_invalid_decimal_string(field: str, bad_val: str):
    c = _candle(**{field: bad_val})
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "INVALID_DECIMAL" in codes
    assert not result.passed


def test_negative_decimal_is_invalid():
    c = _candle(open="-5000")
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "INVALID_DECIMAL" in codes
    assert not result.passed


# -- PRECISION_OVERFLOW ----------------------------------------

def test_precision_overflow_is_warning():
    val = "9" * 39 + ".0"
    c = _candle(open=val)
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "PRECISION_OVERFLOW" in codes
    issue = next(i for i in result.issues if i.code == "PRECISION_OVERFLOW")
    assert issue.severity == "warning"


# -- INVALID_TIMESTAMP -----------------------------------------

@pytest.mark.parametrize("bad_ts", [
    "not-a-date",
    "2024/01/01T12:00:00",
    "2024-01-01 12:00:00",
    "2024-01-01",
    "",
])
def test_invalid_timestamp(bad_ts: str):
    c = _candle(timestamp=bad_ts)
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "INVALID_TIMESTAMP" in codes
    assert not result.passed


# -- OHLC_INVARIANT --------------------------------------------

def test_high_less_than_open():
    c = _candle(high="49000", open="50000")
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "OHLC_INVARIANT" in codes
    assert not result.passed


def test_high_less_than_close():
    c = _candle(high="50000", close="51000")
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "OHLC_INVARIANT" in codes
    assert not result.passed


def test_low_exceeds_open():
    c = _candle(low="51000", open="50000")
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "OHLC_INVARIANT" in codes
    assert not result.passed


def test_low_exceeds_close():
    c = _candle(low="51000", close="50000")
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "OHLC_INVARIANT" in codes
    assert not result.passed


def test_ohlc_invariant_skipped_when_decimals_invalid():
    c = _candle(high="abc", open="50000")
    result = validate_candle_batch([c])
    codes = [i.code for i in result.issues]
    assert "INVALID_DECIMAL" in codes
    assert "OHLC_INVARIANT" not in codes


# -- DUPLICATE_TIMESTAMP ---------------------------------------

def test_duplicate_timestamp_detected():
    candles = [
        _candle(timestamp="2024-01-01T12:00:00"),
        _candle(timestamp="2024-01-01T12:00:00"),
    ]
    result = validate_candle_batch(candles)
    codes = [i.code for i in result.issues]
    assert "DUPLICATE_TIMESTAMP" in codes
    assert not result.passed


def test_same_timestamp_different_exchange_allowed():
    candles = [
        _candle(exchange="exchange_a", timestamp="2024-01-01T12:00:00"),
        _candle(exchange="exchange_b", timestamp="2024-01-01T12:00:00"),
    ]
    result = validate_candle_batch(candles)
    assert result.passed
    assert result.issues == []


def test_same_timestamp_different_symbol_allowed():
    candles = [
        _candle(symbol="BTC/USDT", timestamp="2024-01-01T12:00:00"),
        _candle(symbol="ETH/USDT", timestamp="2024-01-01T12:00:00"),
    ]
    result = validate_candle_batch(candles)
    assert result.passed
    assert result.issues == []


def test_same_timestamp_different_source_allowed():
    candles = [
        _candle(source="provider_a", timestamp="2024-01-01T12:00:00"),
        _candle(source="provider_b", timestamp="2024-01-01T12:00:00"),
    ]
    result = validate_candle_batch(candles)
    assert result.passed
    assert result.issues == []


# -- _decimal_gte ----------------------------------------------

class TestDecimalGte:
    def test_equal(self):
        assert _decimal_gte("1.0", "1.0")

    def test_same_integer_part(self):
        assert _decimal_gte("1.2", "1.1")
        assert not _decimal_gte("1.1", "1.2")

    def test_different_integer_length(self):
        assert _decimal_gte("100", "99")
        assert not _decimal_gte("50", "500")

    def test_same_integer_different_fraction_length(self):
        assert _decimal_gte("1.50", "1.5")
        assert _decimal_gte("1.5", "1.50")
        assert _decimal_gte("1.5", "1.5")

    def test_no_fractional_part(self):
        assert _decimal_gte("5", "3")
        assert not _decimal_gte("2", "5")

    def test_leading_zeros(self):
        assert _decimal_gte("0010", "5")
        assert not _decimal_gte("0005", "0010")


# -- _digit_count ----------------------------------------------

class TestDigitCount:
    def test_integer(self):
        assert _digit_count("12345") == 5

    def test_with_decimal(self):
        assert _digit_count("123.45") == 5

    def test_leading_zeros(self):
        assert _digit_count("00123.45") == 7

    def test_no_digits(self):
        assert _digit_count("0") == 1

    def test_decimal_point_only(self):
        assert _digit_count(".") == 0
