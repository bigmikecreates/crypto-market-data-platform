from datetime import datetime, timezone

import pytest

from crmd_platform.models.candle import Candle
from crmd_platform.providers.gateio import (
    GateioProvider,
    _parse_row,
    _to_gateio_symbol,
    _to_gateio_timeframe,
)
from tests.conftest import load_fixture as _load_fixture


class TestGateioHelpers:
    def test_to_gateio_symbol_native(self) -> None:
        assert _to_gateio_symbol("BTC_USDT") == "BTC_USDT"

    def test_to_gateio_symbol_canonical(self) -> None:
        assert _to_gateio_symbol("BTC/USDT") == "BTC_USDT"

    def test_to_gateio_symbol_eth(self) -> None:
        assert _to_gateio_symbol("ETH/USDT") == "ETH_USDT"

    def test_to_gateio_symbol_lowercase(self) -> None:
        assert _to_gateio_symbol("btc/usdt") == "BTC_USDT"

    def test_to_gateio_timeframe_1m(self) -> None:
        assert _to_gateio_timeframe("1m") == "1m"

    def test_to_gateio_timeframe_5m(self) -> None:
        assert _to_gateio_timeframe("5m") == "5m"

    def test_to_gateio_timeframe_1h(self) -> None:
        assert _to_gateio_timeframe("1h") == "1h"

    def test_to_gateio_timeframe_4h(self) -> None:
        assert _to_gateio_timeframe("4h") == "4h"

    def test_to_gateio_timeframe_1d(self) -> None:
        assert _to_gateio_timeframe("1d") == "1d"

    def test_to_gateio_timeframe_1w(self) -> None:
        assert _to_gateio_timeframe("1w") == "7d"

    def test_to_gateio_timeframe_10s(self) -> None:
        assert _to_gateio_timeframe("10s") == "10s"

    def test_to_gateio_timeframe_30s(self) -> None:
        assert _to_gateio_timeframe("30s") == "30s"

    def test_to_gateio_timeframe_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            _to_gateio_timeframe("99z")


class TestGateioProvider:
    def setup_method(self) -> None:
        self.provider = GateioProvider(rate_limit_sleep=0)
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.end = datetime(2024, 1, 2, tzinfo=timezone.utc)

    def test_provider_is_ohlcv_provider(self) -> None:
        from crmd_platform.providers.base import OHLCVProvider

        assert isinstance(self.provider, OHLCVProvider)

    def test_returns_list_of_candles(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        assert isinstance(rows, list)
        assert len(rows) == 5
        for row in rows:
            assert len(row) == 8

    def test_parse_row_returns_candle(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        c = _parse_row(rows[0], "gateio", "BTC/USDT", "1h", "gateio")
        assert isinstance(c, Candle)
        assert c.exchange == "gateio"
        assert c.symbol == "BTC/USDT"
        assert c.timeframe == "1h"
        assert c.timestamp == "2024-01-01T00:00:00"
        assert c.open == "42250.0"
        assert c.high == "42300.0"
        assert c.low == "42200.0"
        assert c.close == "42255.0"
        assert c.volume == "5217890.5"
        assert c.source == "gateio"

    def test_parse_multiple_rows(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        candles = [_parse_row(r, "gateio", "BTC/USDT", "1h", "gateio") for r in rows]
        assert len(candles) == 5
        assert candles[0].timestamp == "2024-01-01T00:00:00"
        assert candles[1].timestamp == "2024-01-01T01:00:00"
        assert candles[2].timestamp == "2024-01-01T02:00:00"
        assert candles[3].timestamp == "2024-01-01T03:00:00"
        assert candles[4].timestamp == "2024-01-01T04:00:00"

    def test_exchange_and_source_match(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        c = _parse_row(rows[0], "gateio", "BTC/USDT", "1h", "gateio")
        assert c.source == c.exchange

    def test_fixture_timestamps_are_sequential(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        for i in range(1, len(rows)):
            prev_ts = int(rows[i - 1][0])
            curr_ts = int(rows[i][0])
            assert curr_ts > prev_ts
            assert curr_ts - prev_ts == 3_600  # 1 hour in seconds

    def test_field_mapping_close_is_index_2(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        c = _parse_row(rows[0], "gateio", "BTC/USDT", "1h", "gateio")
        assert c.close == rows[0][2]

    def test_field_mapping_high_is_index_3(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        c = _parse_row(rows[0], "gateio", "BTC/USDT", "1h", "gateio")
        assert c.high == rows[0][3]

    def test_field_mapping_open_is_index_5(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        c = _parse_row(rows[0], "gateio", "BTC/USDT", "1h", "gateio")
        assert c.open == rows[0][5]

    def test_field_mapping_low_is_index_4(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        c = _parse_row(rows[0], "gateio", "BTC/USDT", "1h", "gateio")
        assert c.low == rows[0][4]

    def test_field_mapping_volume_is_index_1(self) -> None:
        rows = _load_fixture("gateio_ohlc.json")
        c = _parse_row(rows[0], "gateio", "BTC/USDT", "1h", "gateio")
        assert c.volume == rows[0][1]
