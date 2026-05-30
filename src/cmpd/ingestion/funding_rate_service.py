import sys

from cmpd.config import TimestampConfig
from cmpd.models.funding_rate import FundingRate
from cmpd.storage.parquet_writer import write_funding_rates
from cmpd.validation.funding_rates import (
    validate_funding_rate_batch,
)


class FundingRateService:
    def __init__(
        self,
        ts_config: TimestampConfig | None = None,
    ) -> None:
        self._ts_config = ts_config or TimestampConfig()

    def ingest(
        self,
        rates: list[FundingRate],
        base_path: str = "data",
        merge_strategy: str = "auto",
    ) -> int:
        result = validate_funding_rate_batch(rates)
        if not result.passed:
            for issue in result.issues:
                msg = f"[{issue.severity.upper()}] {issue.code}"
                if issue.candle_index is not None:
                    msg += f" rate[{issue.candle_index}]"
                if issue.field:
                    msg += f" field={issue.field}"
                msg += f": {issue.message}"
                print(msg, file=sys.stderr)
            raise ValueError(
                f"Validation failed with {len(result.issues)} issue(s); no data written."
            )
        write_funding_rates(
            rates,
            base_path=base_path,
            ts_config=self._ts_config,
            merge_strategy=merge_strategy,
        )
        return len(rates)
