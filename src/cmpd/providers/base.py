from abc import ABC, abstractmethod
from datetime import datetime

from cmpd.models.candle import Candle
from cmpd.models.funding_rate import FundingRate


class OHLCVProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]: ...


class FundingRateProvider(ABC):
    @abstractmethod
    def fetch_funding_rates(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[FundingRate]: ...
