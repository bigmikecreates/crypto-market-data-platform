from datetime import datetime

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.providers.base import MarketDataProvider


class FakeProvider(MarketDataProvider):
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        return [
            Candle(
                exchange="fake",
                symbol=symbol,
                timeframe=timeframe,
                timestamp=start.isoformat(),
                open="100",
                high="110",
                low="90",
                close="105",
                volume="10",
                source="fake",
            )
        ]
