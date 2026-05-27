from datetime import datetime

from crypto_market_data_platform.config import TimestampConfig
from crypto_market_data_platform.providers.base import MarketDataProvider
from crypto_market_data_platform.storage.parquet_writer import write_candles


class IngestionService:
    def __init__(
        self,
        provider: MarketDataProvider,
        ts_config: TimestampConfig | None = None,
    ) -> None:
        self._provider = provider
        self._ts_config = ts_config or TimestampConfig()

    def ingest(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        base_path: str = "data",
    ) -> int:
        candles = self._provider.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
        write_candles(candles, base_path=base_path, ts_config=self._ts_config)
        return len(candles)
