import logging
import warnings
from datetime import datetime

from crmd_platform.config import TimestampConfig
from crmd_platform.providers.base import OHLCVProvider
from crmd_platform.storage.backend import StorageBackend, create_backend
from crmd_platform.storage.parquet_writer import write_candles
from crmd_platform.validation.candles import validate_candle_batch

LOG = logging.getLogger(__name__)


class OHLCVService:
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
        backend: StorageBackend | None = None,
    ) -> int:
        """Ingest OHLCV data from provider and write to storage.

        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            start: Start datetime
            end: End datetime
            base_path: Storage path (local path or cloud URI). Deprecated: use backend instead.
            merge_strategy: Merge strategy for existing data
            backend: Storage backend instance. If None, created from base_path.

        Returns:
            Number of candles ingested
        """
        # Deprecation warning for base_path usage
        if backend is None:
            warnings.warn(
                "base_path parameter is deprecated. Use backend parameter instead. "
                "Example: backend=create_backend('s3://bucket/path')",
                DeprecationWarning,
                stacklevel=2,
            )

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
                if issue.record_index is not None:
                    msg += f" candle[{issue.record_index}]"
                if issue.field:
                    msg += f" field={issue.field}"
                msg += f": {issue.message}"
                LOG.error(msg)
            raise ValueError(
                f"Validation failed with {len(result.issues)} issue(s); no data written."
            )

        # Create backend if not provided
        if backend is None:
            backend = create_backend(base_path)

        write_candles(
            candles,
            base_path=base_path,
            ts_config=self._ts_config,
            merge_strategy=merge_strategy,
            backend=backend,
        )
        return len(candles)
