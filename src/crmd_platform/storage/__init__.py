"""Storage backend abstraction for cloud-agnostic Parquet I/O."""

from crmd_platform.storage.backend import (
    AzureBlobBackend,
    LocalStorageBackend,
    StorageBackend,
    create_backend,
)
from crmd_platform.storage.parquet_writer import (
    CANDLE_KEY_COLS,
    FUNDING_RATE_KEY_COLS,
    candle_to_table,
    funding_rate_to_table,
    merge_tables,
    write_candles,
    write_funding_rates,
)

__all__ = [
    # Backend classes
    "StorageBackend",
    "LocalStorageBackend",
    "AzureBlobBackend",
    "create_backend",
    # Writer functions
    "write_candles",
    "write_funding_rates",
    "candle_to_table",
    "funding_rate_to_table",
    "merge_tables",
    # Constants
    "CANDLE_KEY_COLS",
    "FUNDING_RATE_KEY_COLS",
]
