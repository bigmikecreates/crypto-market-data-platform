import json

from scripts.smoke.config import TIMEFRAME


def parse_via_provider(provider: str, raw: str) -> str | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return f"JSON decode error: {e}"

    try:
        if provider == "bitfinex":
            from crmd_platform.providers.bitfinex import _parse_row

            if not isinstance(data, list) or not data:
                return f"expected non-empty list, got {type(data).__name__}"
            _parse_row(data[-1], "bitfinex", "BTC/USD", TIMEFRAME, "smoke")

        elif provider == "bitstamp":
            from crmd_platform.providers.bitstamp import _parse_row

            ohlc = data.get("data", {}).get("ohlc", [])
            if not ohlc:
                return f"no ohlc data; keys={list(data.keys())}"
            _parse_row(ohlc[-1], "bitstamp", "BTC/USD", TIMEFRAME, "smoke")

        elif provider == "bybit":
            from crmd_platform.providers.bybit import _parse_row

            lst = data.get("result", {}).get("list", [])
            if not lst:
                ret = data.get("retCode")
                msg = data.get("retMsg", "")
                return f"no result.list (retCode={ret}, retMsg={msg})"
            _parse_row(lst[-1], "bybit", "BTC/USDT", TIMEFRAME, "smoke")

        elif provider == "kucoin":
            from crmd_platform.providers.kucoin import _parse_row

            candles = data.get("data", [])
            if not candles:
                code = data.get("code", "?")
                return f"no data (code={code})"
            _parse_row(candles[-1], "kucoin", "BTC/USDT", TIMEFRAME, "smoke")

        elif provider == "mexc":
            from crmd_platform.providers.mexc import _parse_row

            if not isinstance(data, list) or not data:
                return f"expected non-empty list, got {type(data).__name__}"
            _parse_row(data[-1], "mexc", "BTC/USDT", TIMEFRAME, "smoke")

        elif provider == "coinbase":
            from crmd_platform.providers.coinbase import _parse_row

            if not isinstance(data, list) or not data:
                return f"expected non-empty list, got {type(data).__name__}"
            _parse_row(data[-1], "coinbase", "BTC/USD", TIMEFRAME, "smoke")

        elif provider == "okx":
            from crmd_platform.providers.okx import _parse_row

            inner = data.get("data", [])
            if not inner:
                code = data.get("code", "?")
                return f"no data (code={code})"
            _parse_row(inner[-1], "okx", "BTC/USDT", TIMEFRAME, "smoke")

        elif provider == "gemini":
            from crmd_platform.providers.gemini import _parse_row

            if not isinstance(data, list) or not data:
                return f"expected non-empty list, got {type(data).__name__}"
            _parse_row(data[-1], "gemini", "BTC/USD", TIMEFRAME, "smoke")

        elif provider == "htx":
            from crmd_platform.providers.htx import _parse_row

            klines = data.get("data", [])
            if not klines:
                status = data.get("status", "?")
                return f"no data (status={status})"
            _parse_row(klines[-1], "htx", "BTC/USDT", TIMEFRAME, "smoke")

        elif provider == "kraken":
            from crmd_platform.providers.kraken import _parse_row

            result = data.get("result", {})
            rows: list = []
            for key, value in result.items():
                if key != "last":
                    if isinstance(value, list):
                        rows = value
                    break
            if not rows:
                errs = data.get("error", [])
                return f"no data; errors={errs}, keys={list(result.keys())}"
            _parse_row(rows[-1], "kraken", "XBT/USD", TIMEFRAME, "smoke")

        else:
            return f"unknown provider: {provider}"

    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return None
