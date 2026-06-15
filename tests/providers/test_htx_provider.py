from datetime import datetime, timezone

import pytest

from crmd_platform.models.candle import Candle
from crmd_platform.providers.htx import (
    HtxProvider,
    _parse_row,
    _to_htx_symbol,
    _to_htx_timeframe,
)
from tests.conftest import load_fixture as _load_fixture


class TestHtxHelpers:
    def test_to_htx_symbol_native(self) -> None:
        assert _to_htx_symbol("btcusdt") == "btcusdt"

    def test_to_htx_symbol_canonical(self) -> None:
        assert _to_htx_symbol("BTC/USDT") == "btcusdt"

    def test_to_htx_symbol_eth(self) -> None:
        assert _to_htx_symbol("ETH/USDT") == "ethusdt"

    def test_to_htx_symbol_lowercase(self) -> None:
        assert _to_htx_symbol("BTC/USD") == "btcusd"

    def test_to_htx_timeframe_1m(self) -> None:
        assert _to_htx_timeframe("1m") == "1min"

    def test_to_htx_timeframe_5m(self) -> None:
        assert _to_htx_timeframe("5m") == "5min"

    def test_to_htx_timeframe_1h(self) -> None:
        assert _to_htx_timeframe("1h") == "60min"

    def test_to_htx_timeframe_4h(self) -> None:
        assert _to_htx_timeframe("4h") == "4hour"

    def test_to_htx_timeframe_1d(self) -> None:
        assert _to_htx_timeframe("1d") == "1day"

    def test_to_htx_timeframe_1w(self) -> None:
        assert _to_htx_timeframe("1w") == "1week"

    def test_to_htx_timeframe_1M(self) -> None:
        assert _to_htx_timeframe("1M") == "1mon"

    def test_to_htx_timeframe_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            _to_htx_timeframe("99z")


class TestHtxProvider:
    def setup_method(self) -> None:
        self.provider = HtxProvider(rate_limit_sleep=0)
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.end = datetime(2024, 1, 2, tzinfo=timezone.utc)

    def test_provider_is_ohlcv_provider(self) -> None:
        from crmd_platform.providers.base import OHLCVProvider

        assert isinstance(self.provider, OHLCVProvider)

    def test_returns_list_of_dicts(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        assert isinstance(rows, list)
        assert len(rows) == 5
        for row in rows:
            assert isinstance(row, dict)
            assert "id" in row

    def test_parse_row_returns_candle(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        c = _parse_row(rows[4], "htx", "BTC/USDT", "1h", "htx")
        assert isinstance(c, Candle)
        assert c.exchange == "htx"
        assert c.symbol == "BTC/USDT"
        assert c.timeframe == "1h"
        assert c.timestamp == "2024-01-01T00:00:00"
        assert c.open == "42100.0"
        assert c.high == "42300.0"
        assert c.low == "42000.0"
        assert c.close == "42250.0"
        assert c.volume == "98.5"
        assert c.source == "htx"

    def test_parse_multiple_rows_reversed(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        rows_reversed = list(reversed(rows))
        candles = [
            _parse_row(r, "htx", "BTC/USDT", "1h", "htx") for r in rows_reversed
        ]
        assert len(candles) == 5
        assert candles[0].timestamp == "2024-01-01T00:00:00"
        assert candles[1].timestamp == "2024-01-01T01:00:00"
        assert candles[2].timestamp == "2024-01-01T02:00:00"
        assert candles[3].timestamp == "2024-01-01T03:00:00"
        assert candles[4].timestamp == "2024-01-01T04:00:00"

    def test_exchange_and_source_match(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        c = _parse_row(rows[4], "htx", "BTC/USDT", "1h", "htx")
        assert c.source == c.exchange

    def test_fixture_timestamps_are_sequential_when_reversed(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        reversed_rows = list(reversed(rows))
        for i in range(1, len(reversed_rows)):
            prev_ts = int(reversed_rows[i - 1]["id"])
            curr_ts = int(reversed_rows[i]["id"])
            assert curr_ts > prev_ts
            assert curr_ts - prev_ts == 3600

    def test_field_mapping_open(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        c = _parse_row(rows[4], "htx", "BTC/USDT", "1h", "htx")
        assert c.open == str(rows[4]["open"])

    def test_field_mapping_high(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        c = _parse_row(rows[4], "htx", "BTC/USDT", "1h", "htx")
        assert c.high == str(rows[4]["high"])

    def test_field_mapping_low(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        c = _parse_row(rows[4], "htx", "BTC/USDT", "1h", "htx")
        assert c.low == str(rows[4]["low"])

    def test_field_mapping_close(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        c = _parse_row(rows[4], "htx", "BTC/USDT", "1h", "htx")
        assert c.close == str(rows[4]["close"])

    def test_field_mapping_volume(self) -> None:
        rows = _load_fixture("htx_ohlc.json")
        c = _parse_row(rows[4], "htx", "BTC/USDT", "1h", "htx")
        assert c.volume == str(rows[4]["amount"])
