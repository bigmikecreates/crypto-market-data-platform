from dataclasses import dataclass, field
from typing import Literal

import pyarrow as pa

CLOUD_SCHEMES = ("s3://", "az://", "abfs://", "gs://")


@dataclass(slots=True)
class TimestampConfig:
    """Timestamp resolution and corresponding Parquet type config."""

    resolution: Literal["s", "us"] = "s"
    format: str = field(init=False)
    parquet_type: pa.DataType = field(init=False)

    def __post_init__(self) -> None:
        if self.resolution == "s":
            self.format = "%Y-%m-%dT%H:%M:%S"
            self.parquet_type = pa.timestamp("s")
        elif self.resolution == "us":
            self.format = "%Y-%m-%dT%H:%M:%S.%f"
            self.parquet_type = pa.timestamp("us")
        else:
            raise ValueError(f"Invalid timestamp resolution: {self.resolution}")



