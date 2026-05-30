import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmpd.models.candle import Candle
from cmpd.providers.bitfinex import (
    BitfinexProvider,
    _parse_row,
    _to_bfx_symbol,
    _to_bfx_timeframe,
)

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> Any:
    path = _FIXTURE_DIR / name
    with open(path) as f:
        return json.load(f)


class TestBitfinexProvider:
    def setup_method(self) -> None:
        self.provider = BitfinexProvider(rate_limit_sleep=0)
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.end = datetime(2024, 1, 2, tzinfo=timezone.utc)

    def test_provider_is_ohlcv_provider(self) -> None:
        from cmpd.providers.base import OHLCVProvider

        assert isinstance(self.provider, OHLCVProvider)

    def test_returns_list_of_candles(self) -> None:
        rows = _load_fixture("bitfinex_ohlc.json")
        assert isinstance(rows, list)
        assert len(rows) == 5
        for row in rows:
            assert len(row) == 6

    def test_parse_row_returns_candle(self) -> None:
        rows = _load_fixture("bitfinex_ohlc.json")
        c = _parse_row(rows[0], "bitfinex", "BTC/USD", "1h", "bitfinex")
        assert isinstance(c, Candle)
        assert c.exchange == "bitfinex"
        assert c.symbol == "BTC/USD"
        assert c.timeframe == "1h"
        assert c.timestamp == "2024-01-01T00:00:00"
        assert c.open == "42250.0"
        assert c.high == "42300.0"
        assert c.low == "42200.0"
        assert c.close == "42255.0"
        assert c.volume == "123.5"
        assert c.source == "bitfinex"

    def test_parse_multiple_rows(self) -> None:
        rows = _load_fixture("bitfinex_ohlc.json")
        candles = [_parse_row(r, "bitfinex", "BTC/USD", "1h", "bitfinex") for r in rows]
        assert len(candles) == 5
        assert candles[0].timestamp == "2024-01-01T00:00:00"
        assert candles[1].timestamp == "2024-01-01T01:00:00"
        assert candles[2].timestamp == "2024-01-01T02:00:00"
        assert candles[3].timestamp == "2024-01-01T03:00:00"
        assert candles[4].timestamp == "2024-01-01T04:00:00"

    def test_exchange_and_source_match(self) -> None:
        rows = _load_fixture("bitfinex_ohlc.json")
        c = _parse_row(rows[0], "bitfinex", "BTC/USD", "1h", "bitfinex")
        assert c.source == c.exchange


class TestBfxHelpers:
    def test_to_bfx_symbol_known(self) -> None:
        assert _to_bfx_symbol("tBTCUSD") == "tBTCUSD"

    def test_to_bfx_symbol_canonical(self) -> None:
        assert _to_bfx_symbol("BTC/USD") == "tBTCUSD"

    def test_to_bfx_symbol_eth(self) -> None:
        assert _to_bfx_symbol("ETH/USD") == "tETHUSD"

    def test_to_bfx_timeframe_1m(self) -> None:
        assert _to_bfx_timeframe("1m") == "1m"

    def test_to_bfx_timeframe_1h(self) -> None:
        assert _to_bfx_timeframe("1h") == "1h"

    def test_to_bfx_timeframe_1d(self) -> None:
        assert _to_bfx_timeframe("1d") == "1D"

    def test_to_bfx_timeframe_1w(self) -> None:
        assert _to_bfx_timeframe("1w") == "1W"

    def test_to_bfx_timeframe_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            _to_bfx_timeframe("99z")

    def test_fixture_timestamps_are_sequential(self) -> None:
        rows = _load_fixture("bitfinex_ohlc.json")
        for i in range(1, len(rows)):
            prev_ts = int(rows[i - 1][0])
            curr_ts = int(rows[i][0])
            assert curr_ts > prev_ts
            assert curr_ts - prev_ts == 3_600_000  # 1 hour in ms
