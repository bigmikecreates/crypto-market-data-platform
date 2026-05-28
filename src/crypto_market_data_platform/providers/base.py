from abc import ABC, abstractmethod
from datetime import datetime

from crypto_market_data_platform.models.candle import Candle


class OHLCVProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]: ...
