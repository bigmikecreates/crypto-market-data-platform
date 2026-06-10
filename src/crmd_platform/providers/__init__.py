from crmd_platform.providers.bitfinex import BitfinexProvider
from crmd_platform.providers.bitstamp import BitstampProvider
from crmd_platform.providers.bybit import BybitProvider
from crmd_platform.providers.fake import FakeProvider
from crmd_platform.providers.gateio import GateioProvider
from crmd_platform.providers.kucoin import KuCoinProvider
from crmd_platform.providers.mexc import MexcProvider

PROVIDERS: dict[str, type] = {
    "fake": FakeProvider,
    "bitfinex": BitfinexProvider,
    "bitstamp": BitstampProvider,
    "kucoin": KuCoinProvider,
    "bybit": BybitProvider,
    "mexc": MexcProvider,
    "gateio": GateioProvider,
}

__all__ = [
    "BitfinexProvider",
    "BitstampProvider",
    "BybitProvider",
    "FakeProvider",
    "GateioProvider",
    "KuCoinProvider",
    "MexcProvider",
    "PROVIDERS",
]
