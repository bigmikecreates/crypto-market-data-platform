"""
Property-based tests for the validation layer.

Strategy: generate Candle/FundingRate instances from constrained domains and
assert that the validator catches invariant violations with 100% recall, and
accepts valid data with 0 false positives.
"""

from hypothesis import assume, given
from hypothesis import strategies as st

from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.validation.candles import validate_candle_batch
from crmd_platform.validation.funding_rates import (
    validate_funding_rate_batch,
)

_FIXED_TS = "2024-01-01T00:00:00"
_FIXED_NFT = "2024-01-01T08:00:00"

# ── Shared primitives ─────────────────────────────────────────────

_positive_cents = st.integers(min_value=1, max_value=10_000_000)
_non_negative_cents = st.integers(min_value=0, max_value=10_000_000)


def _fmt(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


# ── Candle strategies ─────────────────────────────────────────────


@st.composite
def valid_candle(draw, timestamp: str = _FIXED_TS) -> Candle:
    """Generate a Candle that satisfies every validation rule."""
    low_cents = draw(_positive_cents)
    high_cents = draw(
        st.integers(min_value=low_cents, max_value=low_cents + 10_000_000)
    )
    open_cents = draw(st.integers(min_value=low_cents, max_value=high_cents))
    close_cents = draw(st.integers(min_value=low_cents, max_value=high_cents))
    volume_cents = draw(_non_negative_cents)
    return Candle(
        exchange="test",
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=timestamp,
        open=_fmt(open_cents),
        high=_fmt(high_cents),
        low=_fmt(low_cents),
        close=_fmt(close_cents),
        volume=_fmt(volume_cents),
        source="test",
    )


@st.composite
def candle_list(draw, min_size: int = 1, max_size: int = 20) -> list[Candle]:
    """Generate a list of valid Candles with unique timestamps."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    hours = draw(
        st.lists(
            st.integers(min_value=0, max_value=23), min_size=n, max_size=n, unique=True
        )
    )
    result = []
    for h in hours:
        c = draw(valid_candle(timestamp=f"2024-01-01T{h:02d}:00:00"))
        result.append(c)
    return result


# ── Valid candle properties ───────────────────────────────────────


@given(valid_candle())
def test_valid_candle_always_passes(candle: Candle) -> None:
    """Any candle built by the valid_candle strategy must pass validation."""
    result = validate_candle_batch([candle])
    assert result.passed, f"Unexpected issues: {[i.code for i in result.issues]}"


@given(candle_list(min_size=2, max_size=10))
def test_valid_candle_list_passes(candles: list[Candle]) -> None:
    """A list of valid candles with unique timestamps must pass."""
    result = validate_candle_batch(candles)
    assert result.passed, f"Unexpected issues: {[i.code for i in result.issues]}"


# ── OHLC invariant properties ─────────────────────────────────────


@given(
    low_cents=_positive_cents,
    excess=_positive_cents,
)
def test_high_below_low_always_fails(low_cents: int, excess: int) -> None:
    """high < low must always produce an OHLC_INVARIANT error."""
    high_cents = max(1, low_cents - excess)
    assume(high_cents < low_cents)
    candle = Candle(
        exchange="test",
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=_FIXED_TS,
        open=_fmt(high_cents),
        high=_fmt(high_cents),
        low=_fmt(low_cents),
        close=_fmt(high_cents),
        volume="1.00",
        source="test",
    )
    result = validate_candle_batch([candle])
    assert not result.passed
    assert any(i.code == "OHLC_INVARIANT" for i in result.issues)


@given(
    base_cents=_positive_cents,
    excess=_positive_cents,
)
def test_open_below_low_always_fails(base_cents: int, excess: int) -> None:
    """open < low must produce an OHLC_INVARIANT error."""
    low_cents = base_cents + excess
    open_cents = max(1, base_cents)
    assume(open_cents < low_cents)
    candle = Candle(
        exchange="test",
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=_FIXED_TS,
        open=_fmt(open_cents),
        high=_fmt(low_cents + excess),
        low=_fmt(low_cents),
        close=_fmt(low_cents),
        volume="1.00",
        source="test",
    )
    result = validate_candle_batch([candle])
    assert not result.passed
    assert any(i.code == "OHLC_INVARIANT" for i in result.issues)


# ── Negative value properties ─────────────────────────────────────


@given(
    field=st.sampled_from(["open", "high", "low", "close", "volume"]),
    cents=_positive_cents,
)
def test_negative_price_field_always_fails(field: str, cents: int) -> None:
    """A negative value in any OHLCV field must produce a NEGATIVE_VALUE error."""
    kwargs: dict[str, str] = {
        "open": "100.00",
        "high": "110.00",
        "low": "90.00",
        "close": "105.00",
        "volume": "10.00",
    }
    kwargs[field] = f"-{_fmt(cents)}"
    candle = Candle(
        exchange="test",
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=_FIXED_TS,
        source="test",
        **kwargs,
    )
    result = validate_candle_batch([candle])
    assert not result.passed
    assert any(i.code == "NEGATIVE_VALUE" for i in result.issues)


# ── Empty field properties ────────────────────────────────────────


@given(
    field=st.sampled_from(["exchange", "symbol", "timeframe", "timestamp", "source"])
)
def test_empty_string_field_always_fails(field: str) -> None:
    """Any empty string field must produce an EMPTY_FIELD error."""
    kwargs: dict[str, str] = {
        "exchange": "test",
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "timestamp": _FIXED_TS,
        "source": "test",
        "open": "100.00",
        "high": "110.00",
        "low": "90.00",
        "close": "105.00",
        "volume": "10.00",
    }
    kwargs[field] = ""
    candle = Candle(**kwargs)
    result = validate_candle_batch([candle])
    assert not result.passed
    assert any(i.code == "EMPTY_FIELD" for i in result.issues)


@given(
    field=st.sampled_from(["open", "high", "low", "close", "volume"]),
)
def test_empty_decimal_field_always_fails(field: str) -> None:
    """An empty decimal field must fail (EMPTY_FIELD or INVALID_DECIMAL)."""
    kwargs: dict[str, str] = {
        "open": "100.00",
        "high": "110.00",
        "low": "90.00",
        "close": "105.00",
        "volume": "10.00",
    }
    kwargs[field] = ""
    candle = Candle(
        exchange="test",
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=_FIXED_TS,
        source="test",
        **kwargs,
    )
    result = validate_candle_batch([candle])
    assert not result.passed
    issue_codes = {i.code for i in result.issues}
    assert issue_codes & {"EMPTY_FIELD", "INVALID_DECIMAL"}


# ── Duplicate timestamp properties ────────────────────────────────


@given(valid_candle())
def test_duplicate_timestamps_always_fail(candle: Candle) -> None:
    """Two candles with identical keys must produce a DUPLICATE_TIMESTAMP error."""
    result = validate_candle_batch([candle, candle])
    assert not result.passed
    assert any(i.code == "DUPLICATE_TIMESTAMP" for i in result.issues)


# ── FundingRate properties ────────────────────────────────────────


@st.composite
def valid_funding_rate(
    draw, timestamp: str = _FIXED_TS, nft: str = _FIXED_NFT
) -> FundingRate:
    """Generate a FundingRate that satisfies every validation rule."""
    # Rate must be strictly below the ±0.005 cap to avoid FUNDING_RATE_OUT_OF_RANGE.
    # Format is "0.00NN" so max_value=49 gives "0.0049" < "0.005".
    rate_cents = draw(st.integers(min_value=0, max_value=49))
    sign = draw(st.sampled_from(["", "-"]))
    rate_str = f"{sign}0.00{rate_cents:02d}" if rate_cents > 0 else "0.0000"
    predicted_rate_str = f"{sign}0.00{rate_cents:02d}" if rate_cents > 0 else "0.0000"
    return FundingRate(
        exchange="test",
        symbol="BTC/USDT",
        timestamp=timestamp,
        rate=rate_str,
        predicted_rate=predicted_rate_str,
        next_funding_time=nft,
        source="test",
    )


@given(valid_funding_rate())
def test_valid_funding_rate_always_passes(rate: FundingRate) -> None:
    """Any FundingRate built by the valid strategy must pass validation."""
    result = validate_funding_rate_batch([rate])
    assert result.passed, f"Unexpected issues: {[i.code for i in result.issues]}"


@given(valid_funding_rate())
def test_funding_rate_duplicate_timestamp_fails(rate: FundingRate) -> None:
    """Duplicate funding rates must produce a DUPLICATE_TIMESTAMP error."""
    result = validate_funding_rate_batch([rate, rate])
    assert not result.passed
    assert any(i.code == "DUPLICATE_TIMESTAMP" for i in result.issues)


@given(
    ts_hour=st.integers(min_value=1, max_value=23),
)
def test_next_funding_time_before_timestamp_fails(ts_hour: int) -> None:
    """next_funding_time <= timestamp must produce FUTURE_BEFORE_CURRENT."""
    # timestamp is later than next_funding_time
    rate = FundingRate(
        exchange="test",
        symbol="BTC/USDT",
        timestamp=f"2024-01-01T{ts_hour:02d}:00:00",
        rate="0.0001",
        predicted_rate="0.0001",
        next_funding_time="2024-01-01T00:00:00",  # always before ts_hour
        source="test",
    )
    result = validate_funding_rate_batch([rate])
    assert not result.passed
    assert any(i.code == "FUTURE_BEFORE_CURRENT" for i in result.issues)
