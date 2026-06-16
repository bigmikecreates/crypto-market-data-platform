from datetime import datetime, timezone

import pytest

from crmd_platform.models.candle import Candle
from crmd_platform.providers.okx import (
    OkxProvider,
    _parse_row,
    _to_okx_symbol,
    _to_okx_timeframe,
)
from tests.conftest import load_fixture as _load_fixture


class TestOkxHelpers:
    def test_to_okx_symbol_native(self) -> None:
        assert _to_okx_symbol("BTC-USDT") == "BTC-USDT"

    def test_to_okx_symbol_canonical(self) -> None:
        assert _to_okx_symbol("BTC/USDT") == "BTC-USDT"

    def test_to_okx_symbol_eth(self) -> None:
        assert _to_okx_symbol("ETH/USDT") == "ETH-USDT"

    def test_to_okx_symbol_lowercase(self) -> None:
        assert _to_okx_symbol("btc/usdt") == "BTC-USDT"

    def test_to_okx_timeframe_1m(self) -> None:
        assert _to_okx_timeframe("1m") == "1m"

    def test_to_okx_timeframe_5m(self) -> None:
        assert _to_okx_timeframe("5m") == "5m"

    def test_to_okx_timeframe_1h(self) -> None:
        assert _to_okx_timeframe("1h") == "1H"

    def test_to_okx_timeframe_1d(self) -> None:
        assert _to_okx_timeframe("1d") == "1D"

    def test_to_okx_timeframe_1w(self) -> None:
        assert _to_okx_timeframe("1w") == "1W"

    def test_to_okx_timeframe_1M(self) -> None:
        assert _to_okx_timeframe("1M") == "1M"

    def test_to_okx_timeframe_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            _to_okx_timeframe("99z")


class TestOkxProvider:
    def setup_method(self) -> None:
        self.provider = OkxProvider(rate_limit_sleep=0)
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.end = datetime(2024, 1, 2, tzinfo=timezone.utc)

    def test_provider_is_ohlcv_provider(self) -> None:
        from crmd_platform.providers.base import OHLCVProvider

        assert isinstance(self.provider, OHLCVProvider)

    def test_returns_list_of_candles(self) -> None:
        rows = _load_fixture("okx_ohlc.json")
        assert isinstance(rows, list)
        assert len(rows) == 5
        for row in rows:
            assert len(row) == 9

    def test_parse_row_returns_candle(self) -> None:
        rows = _load_fixture("okx_ohlc.json")
        c = _parse_row(rows[4], "okx", "BTC/USDT", "1h", "okx")
        assert isinstance(c, Candle)
        assert c.exchange == "okx"
        assert c.symbol == "BTC/USDT"
        assert c.timeframe == "1h"
        assert c.timestamp == "2024-01-01T00:00:00"
        assert c.open == "42250.0"
        assert c.high == "42300.0"
        assert c.low == "42200.0"
        assert c.close == "42255.0"
        assert c.volume == "123.5"
        assert c.source == "okx"

    def test_parse_multiple_rows(self) -> None:
        rows = _load_fixture("okx_ohlc.json")
        rows_reversed = list(reversed(rows))
        candles = [_parse_row(r, "okx", "BTC/USDT", "1h", "okx") for r in rows_reversed]
        assert len(candles) == 5
        assert candles[0].timestamp == "2024-01-01T00:00:00"
        assert candles[1].timestamp == "2024-01-01T01:00:00"
        assert candles[2].timestamp == "2024-01-01T02:00:00"
        assert candles[3].timestamp == "2024-01-01T03:00:00"
        assert candles[4].timestamp == "2024-01-01T04:00:00"

    def test_exchange_and_source_match(self) -> None:
        rows = _load_fixture("okx_ohlc.json")
        c = _parse_row(rows[4], "okx", "BTC/USDT", "1h", "okx")
        assert c.source == c.exchange

    def test_fixture_timestamps_are_sequential_when_reversed(self) -> None:
        rows = _load_fixture("okx_ohlc.json")
        reversed_rows = list(reversed(rows))
        for i in range(1, len(reversed_rows)):
            prev_ts = int(reversed_rows[i - 1][0])
            curr_ts = int(reversed_rows[i][0])
            assert curr_ts > prev_ts
            assert curr_ts - prev_ts == 3_600_000
