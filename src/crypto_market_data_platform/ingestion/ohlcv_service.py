import sys
from datetime import datetime

from crypto_market_data_platform.config import TimestampConfig
from crypto_market_data_platform.providers.base import OHLCVProvider
from crypto_market_data_platform.storage.parquet_writer import write_candles
from crypto_market_data_platform.validation.candles import validate_candle_batch


class OhlcvService:
    def __init__(
        self,
        provider: OHLCVProvider,
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
        merge_strategy: str = "auto",
    ) -> int:
        candles = self._provider.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
        result = validate_candle_batch(candles)
        if not result.passed:
            for issue in result.issues:
                msg = f"[{issue.severity.upper()}] {issue.code}"
                if issue.candle_index is not None:
                    msg += f" candle[{issue.candle_index}]"
                if issue.field:
                    msg += f" field={issue.field}"
                msg += f": {issue.message}"
                print(msg, file=sys.stderr)
        write_candles(
            candles,
            base_path=base_path,
            ts_config=self._ts_config,
            merge_strategy=merge_strategy,
        )
        return len(candles)
