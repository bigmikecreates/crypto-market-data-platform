from datetime import datetime

SYMBOLS: dict[str, list[str]] = {
    "bitfinex": ["BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"],
    "bitstamp": ["BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"],
    "bybit": ["BTC/USDT", "ETH/USDT", "BTC/USD", "ETH/USD"],
    "kucoin": ["BTC/USDT", "ETH/USDT", "BTC/USD", "ETH/USD"],
    "mexc": ["BTC/USDT", "ETH/USDT", "BTC/USD", "ETH/USD"],
    "coinbase": ["BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"],
    "okx": ["BTC/USDT", "ETH/USDT", "BTC/USD", "ETH/USD"],
    "gemini": ["BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"],
    "htx": ["BTC/USDT", "ETH/USDT"],
    "kraken": ["XBT/USD", "ETH/USD"],
}

API_VERSIONS: dict[str, str] = {
    "bitfinex": "v2",
    "bitstamp": "v2",
    "bybit": "v5",
    "kucoin": "v1",
    "mexc": "v3",
    "coinbase": "v3",
    "okx": "v5",
    "gemini": "v2",
    "htx": "v1",
    "kraken": "0",
}

TIMEFRAME = "1h"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) crypto-market-data-platform/1.0"
OUTPUT_TRUNCATE = 2048


def _utc_ms(dt: datetime) -> str:
    return str(int(dt.timestamp() * 1000))


def _utc_s(dt: datetime) -> str:
    return str(int(dt.timestamp()))


def _endpoint_bitfinex(symbol: str, start: datetime, end: datetime) -> str:
    bfx_sym = f"t{symbol.replace('/', '').upper()}"
    return (
        f"https://api-pub.bitfinex.com/v2/candles/trade:1h:{bfx_sym}/hist"
        f"?start={_utc_ms(start)}&end={_utc_ms(end)}&limit=10&sort=1"
    )


def _endpoint_bitstamp(symbol: str, start: datetime, end: datetime) -> str:
    bs_sym = symbol.replace("/", "").lower()
    return (
        f"https://www.bitstamp.net/api/v2/ohlc/{bs_sym}/"
        f"?step=3600&limit=10&start={_utc_s(start)}&end={_utc_s(end)}"
    )


def _endpoint_bybit(symbol: str, start: datetime, end: datetime) -> str:
    bybit_sym = symbol.replace("/", "").upper()
    return (
        f"https://api.bybit.com/v5/market/kline"
        f"?category=spot&symbol={bybit_sym}&interval=60"
        f"&start={_utc_ms(start)}&end={_utc_ms(end)}&limit=10"
    )


def _endpoint_kucoin(symbol: str, start: datetime, end: datetime) -> str:
    kc_sym = symbol.replace("/", "-").upper()
    return (
        f"https://api.kucoin.com/api/v1/market/candles"
        f"?symbol={kc_sym}&type=1hour&startAt={_utc_s(start)}&endAt={_utc_s(end)}"
    )


def _endpoint_mexc(symbol: str, start: datetime, end: datetime) -> str:
    mexc_sym = symbol.replace("/", "").upper()
    return (
        f"https://api.mexc.com/api/v3/klines"
        f"?symbol={mexc_sym}&interval=1h"
        f"&startTime={_utc_ms(start)}&endTime={_utc_ms(end)}&limit=10"
    )


def _endpoint_coinbase(symbol: str, start: datetime, end: datetime) -> str:
    cb_sym = symbol.replace("/", "-").upper()
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"https://api.exchange.coinbase.com/products/{cb_sym}/candles"
        f"?granularity=3600&start={start_iso}&end={end_iso}"
    )


def _endpoint_okx(symbol: str, start: datetime, end: datetime) -> str:
    okx_sym = symbol.replace("/", "-").upper()
    return f"https://www.okx.com/api/v5/market/candles?instId={okx_sym}&bar=1H&limit=10"


def _endpoint_gemini(symbol: str, start: datetime, end: datetime) -> str:
    gmi_sym = symbol.replace("/", "").upper()
    return f"https://api.gemini.com/v2/candles/{gmi_sym}/1h"


def _endpoint_htx(symbol: str, start: datetime, end: datetime) -> str:
    htx_sym = symbol.replace("/", "").lower()
    return (
        f"https://api.huobi.pro/market/history/kline"
        f"?symbol={htx_sym}&period=60min&size=10"
    )


def _endpoint_kraken(symbol: str, start: datetime, end: datetime) -> str:
    kr_sym = symbol.replace("/", "").upper().replace("BTC", "XBT")
    return f"https://api.kraken.com/0/public/OHLC?pair={kr_sym}&interval=60"


ENDPOINTS = {
    "bitfinex": _endpoint_bitfinex,
    "bitstamp": _endpoint_bitstamp,
    "bybit": _endpoint_bybit,
    "kucoin": _endpoint_kucoin,
    "mexc": _endpoint_mexc,
    "coinbase": _endpoint_coinbase,
    "okx": _endpoint_okx,
    "gemini": _endpoint_gemini,
    "htx": _endpoint_htx,
    "kraken": _endpoint_kraken,
}
