from dataclasses import dataclass


@dataclass(slots=True)
class Candle:
    """A single OHLCV candle with prices and volume stored as strings."""

    exchange: str
    symbol: str
    timeframe: str
    timestamp: str
    open: str
    high: str
    low: str
    close: str
    volume: str
    source: str
