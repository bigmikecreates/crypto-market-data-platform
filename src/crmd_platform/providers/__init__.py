from crmd_platform.providers.bitfinex import BitfinexProvider
from crmd_platform.providers.bitstamp import BitstampProvider
from crmd_platform.providers.bybit import BybitProvider
from crmd_platform.providers.coinbase import CoinbaseProvider
from crmd_platform.providers.fake import FakeProvider
from crmd_platform.providers.gateio import GateioProvider
from crmd_platform.providers.gemini import GeminiProvider
from crmd_platform.providers.htx import HtxProvider
from crmd_platform.providers.kraken import KrakenProvider
from crmd_platform.providers.kucoin import KuCoinProvider
from crmd_platform.providers.mexc import MexcProvider
from crmd_platform.providers.okx import OkxProvider

PROVIDERS: dict[str, type] = {
    "fake": FakeProvider,
    "bitfinex": BitfinexProvider,
    "bitstamp": BitstampProvider,
    "kucoin": KuCoinProvider,
    "bybit": BybitProvider,
    "mexc": MexcProvider,
    "gateio": GateioProvider,
    "coinbase": CoinbaseProvider,
    "okx": OkxProvider,
    "gemini": GeminiProvider,
    "htx": HtxProvider,
    "kraken": KrakenProvider,
}

__all__ = [
    "BitfinexProvider",
    "BitstampProvider",
    "BybitProvider",
    "CoinbaseProvider",
    "FakeProvider",
    "GateioProvider",
    "GeminiProvider",
    "HtxProvider",
    "KrakenProvider",
    "KuCoinProvider",
    "MexcProvider",
    "OkxProvider",
    "PROVIDERS",
]
