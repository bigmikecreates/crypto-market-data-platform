from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from crypto_market_data_platform.config import TimestampConfig
from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate
from crypto_market_data_platform.validation.patterns import _SIGNED_DECIMAL_PATTERN

_DECIMAL128_TYPE = pa.decimal128(38, 10)


def _to_decimal128(values: list[str], label: str, candle_key: str) -> pa.Array:
    for v in values:
        if not _SIGNED_DECIMAL_PATTERN.match(v):
            raise ValueError(
                f"Invalid decimal string '{v}' for {label} in candle {candle_key}"
            )
    arr = pa.array(values, type=pa.string())
    return arr.cast(_DECIMAL128_TYPE, safe=False)


def _to_timestamp(
    values: list[str],
    ts_config: TimestampConfig,
) -> pa.Array:
    arr = pa.array(values, type=pa.string())
    return arr.cast(ts_config.parquet_type)


def _path_for_candle(c: Candle, base_path: str) -> Path:
    date_str = c.timestamp[:10]
    return (
        Path(base_path)
        / c.exchange
        / c.symbol
        / c.timeframe
        / f"{date_str}.parquet"
    )


def candle_to_table(
    candles: list[Candle],
    ts_config: TimestampConfig,
) -> pa.Table:
    if not candles:
        return pa.Table.from_pydict({})

    first = candles[0]
    key = f"{first.exchange}/{first.symbol}/{first.timeframe}"

    return pa.Table.from_pydict(
        {
            "exchange": [c.exchange for c in candles],
            "symbol": [c.symbol for c in candles],
            "timeframe": [c.timeframe for c in candles],
            "timestamp": _to_timestamp([c.timestamp for c in candles], ts_config),
            "open": _to_decimal128([c.open for c in candles], "open", key),
            "high": _to_decimal128([c.high for c in candles], "high", key),
            "low": _to_decimal128([c.low for c in candles], "low", key),
            "close": _to_decimal128([c.close for c in candles], "close", key),
            "volume": _to_decimal128([c.volume for c in candles], "volume", key),
            "source": [c.source for c in candles],
        }
    )


def write_candles(
    candles: list[Candle],
    base_path: str = "data",
    ts_config: TimestampConfig | None = None,
) -> list[Path]:
    if not candles:
        return []

    ts_config = ts_config or TimestampConfig()

    grouped: dict[Path, list[Candle]] = defaultdict(list)
    for c in candles:
        grouped[_path_for_candle(c, base_path)].append(c)

    written: list[Path] = []
    for path, candles_for_path in grouped.items():
        table = candle_to_table(candles_for_path, ts_config)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = pq.read_table(str(path))
            if existing.schema != table.schema:
                existing = existing.cast(table.schema)
            table = pa.concat_tables([existing, table])

        pq.write_table(table, str(path))
        written.append(path)

    return written


def _path_for_funding_rate(r: FundingRate, base_path: str) -> Path:
    date_str = r.timestamp[:10]
    return (
        Path(base_path)
        / r.exchange
        / r.symbol
        / "funding_rate"
        / f"{date_str}.parquet"
    )


def funding_rate_to_table(
    rates: list[FundingRate],
    ts_config: TimestampConfig,
) -> pa.Table:
    if not rates:
        return pa.Table.from_pydict({})

    first = rates[0]
    key = f"{first.exchange}/{first.symbol}/funding_rate"

    return pa.Table.from_pydict(
        {
            "exchange": [r.exchange for r in rates],
            "symbol": [r.symbol for r in rates],
            "timestamp": _to_timestamp([r.timestamp for r in rates], ts_config),
            "rate": _to_decimal128([r.rate for r in rates], "rate", key),
            "predicted_rate": _to_decimal128(
                [r.predicted_rate for r in rates], "predicted_rate", key
            ),
            "next_funding_time": _to_timestamp(
                [r.next_funding_time for r in rates], ts_config
            ),
            "source": [r.source for r in rates],
        }
    )


def write_funding_rates(
    rates: list[FundingRate],
    base_path: str = "data",
    ts_config: TimestampConfig | None = None,
) -> list[Path]:
    if not rates:
        return []

    ts_config = ts_config or TimestampConfig()

    grouped: dict[Path, list[FundingRate]] = defaultdict(list)
    for r in rates:
        grouped[_path_for_funding_rate(r, base_path)].append(r)

    written: list[Path] = []
    for path, rates_for_path in grouped.items():
        table = funding_rate_to_table(rates_for_path, ts_config)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = pq.read_table(str(path))
            if existing.schema != table.schema:
                existing = existing.cast(table.schema)
            table = pa.concat_tables([existing, table])

        pq.write_table(table, str(path))
        written.append(path)

    return written
