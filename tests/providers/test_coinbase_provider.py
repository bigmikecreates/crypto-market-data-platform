from datetime import datetime, timezone

import pytest

from crmd_platform.models.candle import Candle
from crmd_platform.providers.coinbase import (
    CoinbaseProvider,
    _parse_row,
    _to_coinbase_granularity,
    _to_coinbase_symbol,
)
from tests.conftest import load_fixture as _load_fixture


class TestCoinbaseHelpers:
    def test_to_coinbase_symbol_native(self) -> None:
        assert _to_coinbase_symbol("BTC-USDT") == "BTC-USDT"

    def test_to_coinbase_symbol_canonical(self) -> None:
        assert _to_coinbase_symbol("BTC/USDT") == "BTC-USDT"

    def test_to_coinbase_symbol_eth(self) -> None:
        assert _to_coinbase_symbol("ETH/USDT") == "ETH-USDT"

    def test_to_coinbase_symbol_lowercase(self) -> None:
        assert _to_coinbase_symbol("btc/usdt") == "BTC-USDT"

    def test_to_coinbase_granularity_1m(self) -> None:
        assert _to_coinbase_granularity("1m") == 60

    def test_to_coinbase_granularity_5m(self) -> None:
        assert _to_coinbase_granularity("5m") == 300

    def test_to_coinbase_granularity_15m(self) -> None:
        assert _to_coinbase_granularity("15m") == 900

    def test_to_coinbase_granularity_1h(self) -> None:
        assert _to_coinbase_granularity("1h") == 3600

    def test_to_coinbase_granularity_6h(self) -> None:
        assert _to_coinbase_granularity("6h") == 21600

    def test_to_coinbase_granularity_1d(self) -> None:
        assert _to_coinbase_granularity("1d") == 86400

    def test_to_coinbase_granularity_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            _to_coinbase_granularity("2h")


class TestCoinbaseProvider:
    def setup_method(self) -> None:
        self.provider = CoinbaseProvider(rate_limit_sleep=0)
        self.start = datetime(2024, 9, 15, tzinfo=timezone.utc)
        self.end = datetime(2024, 9, 16, tzinfo=timezone.utc)

    def test_provider_is_ohlcv_provider(self) -> None:
        from crmd_platform.providers.base import OHLCVProvider

        assert isinstance(self.provider, OHLCVProvider)

    def test_returns_list_of_candles(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        assert isinstance(rows, list)
        assert len(rows) == 6
        for row in rows:
            assert len(row) == 6

    def test_parse_row_returns_candle(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        c = _parse_row(rows[0], "coinbase", "BTC/USDT", "1h", "coinbase")
        assert isinstance(c, Candle)
        assert c.exchange == "coinbase"
        assert c.symbol == "BTC/USDT"
        assert c.timeframe == "1h"
        assert c.timestamp == "2024-09-15T19:00:00"
        assert c.open == "59200.0"
        assert c.high == "60200.0"
        assert c.low == "58700.0"
        assert c.close == "59500.0"
        assert c.volume == "91.8"
        assert c.source == "coinbase"

    def test_parse_multiple_rows(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        candles = [
            _parse_row(r, "coinbase", "BTC/USDT", "1h", "coinbase") for r in rows
        ]
        assert len(candles) == 6
        for i in range(1, len(candles)):
            assert candles[i].timestamp > candles[i - 1].timestamp
            curr = int(rows[i][0])
            prev = int(rows[i - 1][0])
            assert (curr - prev) == 3600

    def test_exchange_and_source_match(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        c = _parse_row(rows[0], "coinbase", "BTC/USDT", "1h", "coinbase")
        assert c.source == c.exchange

    def test_fixture_timestamps_are_sequential(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        for i in range(1, len(rows)):
            prev_ts = int(rows[i - 1][0])
            curr_ts = int(rows[i][0])
            assert curr_ts > prev_ts
            assert curr_ts - prev_ts == 3600

    def test_field_mapping_open_is_index_3(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        c = _parse_row(rows[1], "coinbase", "BTC/USDT", "1h", "coinbase")
        assert c.open == str(rows[1][3])

    def test_field_mapping_high_is_index_2(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        c = _parse_row(rows[1], "coinbase", "BTC/USDT", "1h", "coinbase")
        assert c.high == str(rows[1][2])

    def test_field_mapping_low_is_index_1(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        c = _parse_row(rows[1], "coinbase", "BTC/USDT", "1h", "coinbase")
        assert c.low == str(rows[1][1])

    def test_field_mapping_close_is_index_4(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        c = _parse_row(rows[1], "coinbase", "BTC/USDT", "1h", "coinbase")
        assert c.close == str(rows[1][4])

    def test_field_mapping_volume_is_index_5(self) -> None:
        rows = _load_fixture("coinbase_ohlc.json")
        c = _parse_row(rows[1], "coinbase", "BTC/USDT", "1h", "coinbase")
        assert c.volume == str(rows[1][5])
