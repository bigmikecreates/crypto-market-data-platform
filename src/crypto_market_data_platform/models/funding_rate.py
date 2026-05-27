from dataclasses import dataclass


@dataclass(slots=True)
class FundingRate:
    exchange: str
    symbol: str
    timestamp: str
    rate: str
    predicted_rate: str
    next_funding_time: str
    source: str
