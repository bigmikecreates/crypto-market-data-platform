from datetime import datetime, timedelta

from cmpd.models.candle import Candle
from cmpd.models.funding_rate import FundingRate
from cmpd.providers.base import (
    FundingRateProvider,
    OHLCVProvider,
)


class FakeProvider(OHLCVProvider, FundingRateProvider):
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
        nft = start + timedelta(hours=8)
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
