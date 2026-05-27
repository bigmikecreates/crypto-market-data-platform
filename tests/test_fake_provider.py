from datetime import datetime

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.fake import FakeProvider


class TestFakeProvider:
    def setup_method(self) -> None:
        self.provider = FakeProvider()
        self.start = datetime(2026, 5, 27)
        self.end = datetime(2026, 5, 28)

    def test_returns_list_of_candles(self) -> None:
        result = self.provider.fetch_ohlcv(
            symbol="BTC/USDT",
            timeframe="1h",
            start=self.start,
            end=self.end,
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Candle)

    def test_candle_field_types(self) -> None:
        result = self.provider.fetch_ohlcv(
            symbol="ETH/USDT",
            timeframe="1d",
            start=self.start,
            end=self.end,
        )
        c = result[0]
        assert isinstance(c.exchange, str)
        assert isinstance(c.symbol, str)
        assert isinstance(c.timeframe, str)
        assert isinstance(c.timestamp, str)
        assert isinstance(c.open, str)
        assert isinstance(c.high, str)
        assert isinstance(c.low, str)
        assert isinstance(c.close, str)
        assert isinstance(c.volume, str)
        assert isinstance(c.source, str)

    def test_hardcoded_values(self) -> None:
        result = self.provider.fetch_ohlcv(
            symbol="BTC/USDT",
            timeframe="1h",
            start=self.start,
            end=self.end,
        )
        c = result[0]
        assert c.exchange == "fake"
        assert c.symbol == "BTC/USDT"
        assert c.timeframe == "1h"
        assert c.timestamp == self.start.strftime("%Y-%m-%dT%H:%M:%S")
        assert c.open == "100"
        assert c.high == "110"
        assert c.low == "90"
        assert c.close == "105"
        assert c.volume == "10"
        assert c.source == "fake"

    def test_source_and_exchange_match(self) -> None:
        result = self.provider.fetch_ohlcv(
            symbol="BTC/USDT",
            timeframe="1h",
            start=self.start,
            end=self.end,
        )
        c = result[0]
        assert c.source == c.exchange
