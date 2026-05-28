import json

from scripts.smoke.config import TIMEFRAME


def parse_via_provider(provider: str, raw: str) -> str | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return f"JSON decode error: {e}"

    try:
        if provider == "bitfinex":
            from crypto_market_data_platform.providers.bitfinex import _parse_row

            if not isinstance(data, list) or not data:
                return f"expected non-empty list, got {type(data).__name__}"
            _parse_row(data[-1], "bitfinex", "BTC/USD", TIMEFRAME, "smoke")

        elif provider == "bitstamp":
            from crypto_market_data_platform.providers.bitstamp import _parse_row

            ohlc = data.get("data", {}).get("ohlc", [])
            if not ohlc:
                return f"no ohlc data; keys={list(data.keys())}"
            _parse_row(ohlc[-1], "bitstamp", "BTC/USD", TIMEFRAME, "smoke")

        elif provider == "bybit":
            from crypto_market_data_platform.providers.bybit import _parse_row

            lst = data.get("result", {}).get("list", [])
            if not lst:
                ret = data.get("retCode")
                msg = data.get("retMsg", "")
                return f"no result.list (retCode={ret}, retMsg={msg})"
            _parse_row(lst[-1], "bybit", "BTC/USDT", TIMEFRAME, "smoke")

        elif provider == "kucoin":
            from crypto_market_data_platform.providers.kucoin import _parse_row

            candles = data.get("data", [])
            if not candles:
                code = data.get("code", "?")
                return f"no data (code={code})"
            _parse_row(candles[-1], "kucoin", "BTC/USDT", TIMEFRAME, "smoke")

        elif provider == "mexc":
            from crypto_market_data_platform.providers.mexc import _parse_row

            if not isinstance(data, list) or not data:
                return f"expected non-empty list, got {type(data).__name__}"
            _parse_row(data[-1], "mexc", "BTC/USDT", TIMEFRAME, "smoke")

        else:
            return f"unknown provider: {provider}"

    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return None
