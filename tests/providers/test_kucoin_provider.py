import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.kucoin import (
    KuCoinProvider,
    _parse_row,
    _to_kc_symbol,
    _to_kc_timeframe,
)

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> Any:
    path = _FIXTURE_DIR / name
    with open(path) as f:
        return json.load(f)


class TestKuCoinProvider:
    def setup_method(self) -> None:
        self.provider = KuCoinProvider(rate_limit_sleep=0)
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.end = datetime(2024, 1, 2, tzinfo=timezone.utc)

    def test_provider_is_market_data_provider(self) -> None:
        from crypto_market_data_platform.providers.base import MarketDataProvider
        assert isinstance(self.provider, MarketDataProvider)

    def test_returns_list_of_candles(self) -> None:
        rows = _load_fixture("kucoin_ohlc.json")
        assert isinstance(rows, list)
        assert len(rows) == 5
        for row in rows:
            assert len(row) == 7

    def test_parse_row_returns_candle(self) -> None:
        rows = _load_fixture("kucoin_ohlc.json")
        c = _parse_row(rows[0], "kucoin", "BTC/USDT", "1h", "kucoin")
        assert isinstance(c, Candle)
        assert c.exchange == "kucoin"
        assert c.symbol == "BTC/USDT"
        assert c.timeframe == "1h"
        assert c.timestamp == "2024-01-01T00:00:00"
        assert c.open == "42250.0"
        assert c.high == "42300.0"
        assert c.low == "42200.0"
        assert c.close == "42255.0"
        assert c.volume == "123.5"
        assert c.source == "kucoin"

    def test_parse_multiple_rows(self) -> None:
        rows = _load_fixture("kucoin_ohlc.json")
        candles = [_parse_row(r, "kucoin", "BTC/USDT", "1h", "kucoin") for r in rows]
        assert len(candles) == 5
        assert candles[0].timestamp == "2024-01-01T00:00:00"
        assert candles[1].timestamp == "2024-01-01T01:00:00"
        assert candles[2].timestamp == "2024-01-01T02:00:00"
        assert candles[3].timestamp == "2024-01-01T03:00:00"
        assert candles[4].timestamp == "2024-01-01T04:00:00"

    def test_exchange_and_source_match(self) -> None:
        rows = _load_fixture("kucoin_ohlc.json")
        c = _parse_row(rows[0], "kucoin", "BTC/USDT", "1h", "kucoin")
        assert c.source == c.exchange


class TestKcHelpers:
    def test_to_kc_symbol_native(self) -> None:
        assert _to_kc_symbol("BTC-USDT") == "BTC-USDT"

    def test_to_kc_symbol_canonical(self) -> None:
        assert _to_kc_symbol("BTC/USDT") == "BTC-USDT"

    def test_to_kc_symbol_eth(self) -> None:
        assert _to_kc_symbol("ETH/USDT") == "ETH-USDT"

    def test_to_kc_symbol_lowercase(self) -> None:
        assert _to_kc_symbol("btc-usdt") == "BTC-USDT"

    def test_to_kc_symbol_lowercase_canonical(self) -> None:
        assert _to_kc_symbol("btc/usdt") == "BTC-USDT"

    def test_to_kc_timeframe_1m(self) -> None:
        assert _to_kc_timeframe("1m") == "1min"

    def test_to_kc_timeframe_5m(self) -> None:
        assert _to_kc_timeframe("5m") == "5min"

    def test_to_kc_timeframe_1h(self) -> None:
        assert _to_kc_timeframe("1h") == "1hour"

    def test_to_kc_timeframe_1d(self) -> None:
        assert _to_kc_timeframe("1d") == "1day"

    def test_to_kc_timeframe_1w(self) -> None:
        assert _to_kc_timeframe("1w") == "1week"

    def test_to_kc_timeframe_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            _to_kc_timeframe("99z")

    def test_fixture_timestamps_are_sequential(self) -> None:
        rows = _load_fixture("kucoin_ohlc.json")
        for i in range(1, len(rows)):
            prev_ts = int(rows[i - 1][0])
            curr_ts = int(rows[i][0])
            assert curr_ts > prev_ts
            assert curr_ts - prev_ts == 3600  # 1 hour in seconds
