import json
from pathlib import Path
from typing import Any

from crmd_platform.models.candle import Candle


_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    path = _FIXTURE_DIR / name
    with open(path) as f:
        return json.load(f)


def make_candle(
    timestamp: str,
    exchange: str = "fake",
    symbol: str = "BTC-USD",
    timeframe: str = "1h",
    open_str: str = "50000.00",
    high: str = "51000.00",
    low: str = "49000.00",
    close: str = "50500.00",
    volume: str = "100.5",
    source: str = "test",
) -> Candle:
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_str,
        high=high,
        low=low,
        close=close,
        volume=volume,
        source=source,
    )
