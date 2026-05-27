from dataclasses import dataclass, field

import pyarrow as pa


@dataclass(slots=True)
class TimestampConfig:
    """Timestamp resolution and corresponding Parquet type config."""

    resolution: str = "s"
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
