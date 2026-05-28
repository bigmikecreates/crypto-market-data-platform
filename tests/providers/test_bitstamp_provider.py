import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.bitstamp import (
    BitstampProvider,
    _parse_row,
    _to_bitstamp_symbol,
    _to_bitstamp_step,
)

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> Any:
    path = _FIXTURE_DIR / name
    with open(path) as f:
        return json.load(f)


class TestBitstampHelpers:
    def test_to_bitstamp_symbol_native(self) -> None:
        assert _to_bitstamp_symbol("btcusd") == "btcusd"

    def test_to_bitstamp_symbol_canonical(self) -> None:
        assert _to_bitstamp_symbol("BTC/USD") == "btcusd"

    def test_to_bitstamp_symbol_eth(self) -> None:
        assert _to_bitstamp_symbol("ETH/USD") == "ethusd"

    def test_to_bitstamp_symbol_usdt(self) -> None:
        assert _to_bitstamp_symbol("BTC/USDT") == "btcusdt"

    def test_to_bitstamp_step_1m(self) -> None:
        assert _to_bitstamp_step("1m") == 60

    def test_to_bitstamp_step_5m(self) -> None:
        assert _to_bitstamp_step("5m") == 300

    def test_to_bitstamp_step_15m(self) -> None:
        assert _to_bitstamp_step("15m") == 900

    def test_to_bitstamp_step_1h(self) -> None:
        assert _to_bitstamp_step("1h") == 3600

    def test_to_bitstamp_step_4h(self) -> None:
        assert _to_bitstamp_step("4h") == 14400

    def test_to_bitstamp_step_1d(self) -> None:
        assert _to_bitstamp_step("1d") == 86400

    def test_to_bitstamp_step_3d(self) -> None:
        assert _to_bitstamp_step("3d") == 259200

    def test_to_bitstamp_step_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            _to_bitstamp_step("99z")


class TestBitstampProvider:
    def setup_method(self) -> None:
        self.provider = BitstampProvider(rate_limit_sleep=0)
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.end = datetime(2024, 1, 2, tzinfo=timezone.utc)

    def test_provider_is_ohlcv_provider(self) -> None:
        from crypto_market_data_platform.providers.base import OHLCVProvider
        assert isinstance(self.provider, OHLCVProvider)

    def test_returns_list_of_candles(self) -> None:
        data = _load_fixture("bitstamp_ohlc.json")
        ohlc = data["data"]["ohlc"]
        assert isinstance(ohlc, list)
        assert len(ohlc) == 5
        for row in ohlc:
            assert set(row.keys()) == {"timestamp", "open", "high", "low", "close", "volume"}

    def test_parse_row_returns_candle(self) -> None:
        data = _load_fixture("bitstamp_ohlc.json")
        row = data["data"]["ohlc"][0]
        c = _parse_row(row, "bitstamp", "BTC/USD", "1h", "bitstamp")
        assert isinstance(c, Candle)
        assert c.exchange == "bitstamp"
        assert c.symbol == "BTC/USD"
        assert c.timeframe == "1h"
        assert c.timestamp == "2024-01-01T00:00:00"
        assert c.open == "42250.0"
        assert c.high == "42300.0"
        assert c.low == "42200.0"
        assert c.close == "42255.0"
        assert c.volume == "123.5"
        assert c.source == "bitstamp"

    def test_parse_multiple_rows(self) -> None:
        data = _load_fixture("bitstamp_ohlc.json")
        rows = data["data"]["ohlc"]
        candles = [_parse_row(r, "bitstamp", "BTC/USD", "1h", "bitstamp") for r in rows]
        assert len(candles) == 5
        assert candles[0].timestamp == "2024-01-01T00:00:00"
        assert candles[1].timestamp == "2024-01-01T01:00:00"
        assert candles[2].timestamp == "2024-01-01T02:00:00"
        assert candles[3].timestamp == "2024-01-01T03:00:00"
        assert candles[4].timestamp == "2024-01-01T04:00:00"

    def test_exchange_and_source_match(self) -> None:
        data = _load_fixture("bitstamp_ohlc.json")
        row = data["data"]["ohlc"][0]
        c = _parse_row(row, "bitstamp", "BTC/USD", "1h", "bitstamp")
        assert c.source == c.exchange

    def test_fixture_timestamps_are_sequential(self) -> None:
        data = _load_fixture("bitstamp_ohlc.json")
        rows = data["data"]["ohlc"]
        for i in range(1, len(rows)):
            prev_ts = int(rows[i - 1]["timestamp"])
            curr_ts = int(rows[i]["timestamp"])
            assert curr_ts > prev_ts
            assert curr_ts - prev_ts == 3600
