from datetime import datetime, timezone

import pytest

from crmd_platform.models.candle import Candle
from crmd_platform.providers.kraken import (
    KrakenProvider,
    _parse_row,
    _to_kraken_interval,
    _to_kraken_symbol,
)
from tests.conftest import load_fixture as _load_fixture


class TestKrakenHelpers:
    def test_to_kraken_symbol_btc(self) -> None:
        assert _to_kraken_symbol("BTC/USD") == "XBTUSD"

    def test_to_kraken_symbol_eth(self) -> None:
        assert _to_kraken_symbol("ETH/USD") == "ETHUSD"

    def test_to_kraken_symbol_lowercase(self) -> None:
        assert _to_kraken_symbol("btc/usd") == "XBTUSD"

    def test_to_kraken_symbol_xbt(self) -> None:
        assert _to_kraken_symbol("XBT/USD") == "XBTUSD"

    def test_to_kraken_symbol_btc_usdt(self) -> None:
        assert _to_kraken_symbol("BTC/USDT") == "XBTUSDT"

    def test_to_kraken_interval_1m(self) -> None:
        assert _to_kraken_interval("1m") == 1

    def test_to_kraken_interval_5m(self) -> None:
        assert _to_kraken_interval("5m") == 5

    def test_to_kraken_interval_1h(self) -> None:
        assert _to_kraken_interval("1h") == 60

    def test_to_kraken_interval_4h(self) -> None:
        assert _to_kraken_interval("4h") == 240

    def test_to_kraken_interval_1d(self) -> None:
        assert _to_kraken_interval("1d") == 1440

    def test_to_kraken_interval_1w(self) -> None:
        assert _to_kraken_interval("1w") == 10080

    def test_to_kraken_interval_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            _to_kraken_interval("99z")


class TestKrakenProvider:
    def setup_method(self) -> None:
        self.provider = KrakenProvider(rate_limit_sleep=0)
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.end = datetime(2024, 1, 2, tzinfo=timezone.utc)

    def test_provider_is_ohlcv_provider(self) -> None:
        from crmd_platform.providers.base import OHLCVProvider

        assert isinstance(self.provider, OHLCVProvider)

    def test_returns_list_of_candles(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        assert isinstance(rows, list)
        assert len(rows) == 5
        for row in rows:
            assert len(row) == 8

    def test_parse_row_returns_candle(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        c = _parse_row(rows[0], "kraken", "XBT/USD", "1h", "kraken")
        assert isinstance(c, Candle)
        assert c.exchange == "kraken"
        assert c.symbol == "XBT/USD"
        assert c.timeframe == "1h"
        assert c.timestamp == "2024-01-01T00:00:00"
        assert c.open == "42100.0"
        assert c.high == "42300.0"
        assert c.low == "42000.0"
        assert c.close == "42250.0"
        assert c.volume == "98.5"
        assert c.source == "kraken"

    def test_parse_multiple_rows(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        candles = [
            _parse_row(r, "kraken", "XBT/USD", "1h", "kraken") for r in rows
        ]
        assert len(candles) == 5
        assert candles[0].timestamp == "2024-01-01T00:00:00"
        assert candles[1].timestamp == "2024-01-01T01:00:00"
        assert candles[2].timestamp == "2024-01-01T02:00:00"
        assert candles[3].timestamp == "2024-01-01T03:00:00"
        assert candles[4].timestamp == "2024-01-01T04:00:00"

    def test_exchange_and_source_match(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        c = _parse_row(rows[0], "kraken", "XBT/USD", "1h", "kraken")
        assert c.source == c.exchange

    def test_fixture_timestamps_are_sequential(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        for i in range(1, len(rows)):
            prev_ts = int(rows[i - 1][0])
            curr_ts = int(rows[i][0])
            assert curr_ts > prev_ts
            assert curr_ts - prev_ts == 3600

    def test_volume_is_index_6(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        c = _parse_row(rows[0], "kraken", "XBT/USD", "1h", "kraken")
        assert c.volume == str(rows[0][6])

    def test_field_mapping_open(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        c = _parse_row(rows[0], "kraken", "XBT/USD", "1h", "kraken")
        assert c.open == str(rows[0][1])

    def test_field_mapping_high(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        c = _parse_row(rows[0], "kraken", "XBT/USD", "1h", "kraken")
        assert c.high == str(rows[0][2])

    def test_field_mapping_low(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        c = _parse_row(rows[0], "kraken", "XBT/USD", "1h", "kraken")
        assert c.low == str(rows[0][3])

    def test_field_mapping_close(self) -> None:
        rows = _load_fixture("kraken_ohlc.json")
        c = _parse_row(rows[0], "kraken", "XBT/USD", "1h", "kraken")
        assert c.close == str(rows[0][4])
