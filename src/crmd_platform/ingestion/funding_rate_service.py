import logging
from datetime import datetime

from crmd_platform.config import TimestampConfig
from crmd_platform.providers.base import FundingRateProvider
from crmd_platform.storage.backend import StorageBackend, create_backend
from crmd_platform.storage.parquet_writer import write_funding_rates
from crmd_platform.validation.funding_rates import (
    validate_funding_rate_batch,
)

LOG = logging.getLogger(__name__)


class FundingRateService:
    def __init__(
        self,
        provider: FundingRateProvider,
        ts_config: TimestampConfig | None = None,
    ) -> None:
        self._provider = provider
        self._ts_config = ts_config or TimestampConfig()

    def ingest(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        base_path: str = "data",
        merge_strategy: str = "auto",
        backend: StorageBackend | None = None,
    ) -> int:
        """Ingest funding rates from provider and write to storage.

        Args:
            symbol: Trading pair symbol
            start: Start datetime
            end: End datetime
            base_path: Storage path (local path or cloud URI). Ignored if backend is provided.
            merge_strategy: Merge strategy for existing data
            backend: Storage backend instance. If None, created from base_path.

        Returns:
            Number of funding rates ingested
        """
        rates = self._provider.fetch_funding_rates(
            symbol=symbol,
            start=start,
            end=end,
        )
        result = validate_funding_rate_batch(rates)
        if not result.passed:
            for issue in result.issues:
                msg = f"[{issue.severity.upper()}] {issue.code}"
                if issue.record_index is not None:
                    msg += f" rate[{issue.record_index}]"
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

        write_funding_rates(
            rates,
            base_path=base_path,
            ts_config=self._ts_config,
            merge_strategy=merge_strategy,
            backend=backend,
        )
        return len(rates)
