from datetime import datetime, timezone

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate
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
                timestamp=start.strftime("%Y-%m-%dT%H:%M:%S"),
                open="100",
                high="110",
                low="90",
                close="105",
                volume="10",
                source="fake",
            )
        ]

    def fetch_funding_rates(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[FundingRate]:
        nft = datetime(2026, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
        return [
            FundingRate(
                exchange="fake",
                symbol=symbol,
                timestamp=start.strftime("%Y-%m-%dT%H:%M:%S"),
                rate="0.0001",
                predicted_rate="0.0002",
                next_funding_time=nft.strftime("%Y-%m-%dT%H:%M:%S"),
                source="fake",
            )
        ]
