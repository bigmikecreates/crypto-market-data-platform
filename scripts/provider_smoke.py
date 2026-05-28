#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────
# Provider smoke test — live API calls to verify each provider's
# response can still be parsed by the current provider code.
#
# Usage:
#   python scripts/provider_smoke.py --provider bitfinex
#   python scripts/provider_smoke.py --provider bitfinex --format markdown
#
# Exit code: 0 if passed (≤1 failure), 1 if failed (≥2 failures).
# ─────────────────────────────────────────────────────────────────────

import json
import re
import sys
import traceback
import urllib.error
import urllib.request
from argparse import ArgumentParser, Namespace
from datetime import datetime, timezone
from typing import Any

SYMBOLS: dict[str, list[str]] = {
    "bitfinex": ["BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"],
    "bitstamp": ["BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"],
    "bybit":    ["BTC/USDT", "ETH/USDT", "BTC/USD", "ETH/USD"],
    "kucoin":   ["BTC/USDT", "ETH/USDT", "BTC/USD", "ETH/USD"],
    "mexc":     ["BTC/USDT", "ETH/USDT", "BTC/USD", "ETH/USD"],
}

TIMEFRAME = "1h"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) crypto-market-data-platform/1.0"
OUTPUT_TRUNCATE = 2048

# ── URL builders (replicates provider URL construction) ───────────


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


ENDPOINTS = {
    "bitfinex": _endpoint_bitfinex,
    "bitstamp": _endpoint_bitstamp,
    "bybit":    _endpoint_bybit,
    "kucoin":   _endpoint_kucoin,
    "mexc":     _endpoint_mexc,
}

API_VERSIONS = {
    "bitfinex": "v2",
    "bitstamp": "v2",
    "bybit":    "v5",
    "kucoin":   "v1",
    "mexc":     "v3",
}

# ── parsing via provider _parse_row ────────────────────────────────


def _parse_via_provider(provider: str, raw: str) -> str | None:
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
                return f"no data (code={code}); keys={list(data.keys())}"
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


def _detect_api_version(
    original_url: str, final_url: str, configured: str
) -> dict[str, str]:
    result: dict[str, str] = {"old": configured, "new": "unknown", "detected_via": ""}
    if original_url == final_url:
        return result
    pattern = r"/(v\d+)/"
    orig_match = re.search(pattern, original_url)
    final_match = re.search(pattern, final_url)
    if orig_match and final_match:
        orig_v = orig_match.group(1)
        final_v = final_match.group(1)
        if orig_v != final_v:
            result["new"] = final_v
            result["detected_via"] = "redirect"
        return result
    result["detected_via"] = f"redirect: {original_url} → {final_url}"
    return result


# ── core logic ─────────────────────────────────────────────────────

AttemptResult = dict[str, Any]


def _attempt(provider: str, symbol: str, attempt_num: int) -> AttemptResult:
    now = datetime.now(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0)
    start = end.replace(hour=end.hour - 1)

    url_builder = ENDPOINTS[provider]
    url = url_builder(symbol, start, end)

    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })

    attempt: AttemptResult = {
        "attempt": attempt_num,
        "symbol": symbol,
        "http_status": None,
        "raw": None,
        "error": None,
        "final_url": url,
        "outcome": "unknown",
    }

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            attempt["http_status"] = resp.status
            attempt["final_url"] = resp.url
            raw = resp.read().decode("utf-8")
            attempt["raw"] = raw[:OUTPUT_TRUNCATE]
            parse_err = _parse_via_provider(provider, raw)
            if parse_err:
                attempt["error"] = parse_err
                attempt["outcome"] = "parse_error"
            else:
                attempt["outcome"] = "ok"
    except urllib.error.HTTPError as e:
        attempt["http_status"] = e.code
        body = e.read().decode("utf-8", errors="replace")
        attempt["raw"] = body[:OUTPUT_TRUNCATE]
        attempt["error"] = f"HTTP {e.code}: {e.reason}"
        attempt["outcome"] = "http_error"
    except urllib.error.URLError as e:
        attempt["error"] = f"URL error: {e.reason}"
        attempt["outcome"] = "network_error"
    except Exception as e:
        attempt["error"] = f"{type(e).__name__}: {e}"
        attempt["outcome"] = "exception"

    return attempt


def smoke_provider(provider: str) -> dict[str, Any]:
    symbols = SYMBOLS[provider]
    configured_version = API_VERSIONS[provider]
    attempts: list[AttemptResult] = []
    success_count = 0
    failure_count = 0

    for i in range(3):
        sym = symbols[min(i, len(symbols) - 1)]
        result = _attempt(provider, sym, i + 1)
        attempts.append(result)
        if result["outcome"] == "ok":
            success_count += 1
        else:
            failure_count += 1

    now = datetime.now(timezone.utc)
    first_url = ENDPOINTS[provider](symbols[0], now, now)
    last_url = attempts[-1]["final_url"]
    version_info = _detect_api_version(first_url, last_url, configured_version)

    passed = failure_count < 2

    return {
        "provider": provider,
        "passed": passed,
        "configured_version": configured_version,
        "version_info": version_info,
        "attempts": attempts,
        "success_count": success_count,
        "failure_count": failure_count,
    }


# ── formatting ─────────────────────────────────────────────────────


def _attempt_row(a: AttemptResult) -> str:
    sym = a["symbol"]
    outcome = a["outcome"]
    if outcome == "ok":
        return f"  ✅  Attempt {a['attempt']}: {sym} – HTTP {a['http_status']} – Parse OK"
    err = a["error"] or "unknown"
    return f"  ❌  Attempt {a['attempt']}: {sym} – HTTP {a['http_status'] or 'N/A'} – {err}"


def format_text(result: dict[str, Any]) -> str:
    v = result["version_info"]
    lines = [
        f"Provider smoke test: {result['provider']}",
        f"  API version: old={v['old']}, detected={v['new']} ({v['detected_via'] or 'unchanged'})",
        f"  Outcome: {'PASS' if result['passed'] else 'FAIL'}",
        f"  ({result['success_count']}/3 passed, {result['failure_count']}/3 failed)",
        "",
    ]
    for a in result["attempts"]:
        lines.append(_attempt_row(a))
    lines.append("")
    return "\n".join(lines)


def format_markdown(result: dict[str, Any]) -> str:
    provider = result["provider"]
    v = result["version_info"]
    lines = [
        f"## Provider smoke test failure",
        "",
        f"**Provider:** {provider}",
        f"**Date:** {datetime.now(timezone.utc).isoformat()}Z",
        "",
        "### API version",
        f"- **Old (configured):** {v['old']}",
        f"- **Detected (from response):** {v['new']}",
        f"  - Via: {v['detected_via'] or 'unchanged'}",
        "",
        "### Attempts",
        "| # | Symbol | HTTP | Outcome |",
        "|---|--------|------|---------|",
    ]
    for a in result["attempts"]:
        status = "Parse OK" if a["outcome"] == "ok" else (a["error"] or "?")
        http = str(a["http_status"]) if a["http_status"] else "N/A"
        lines.append(f"| {a['attempt']} | {a['symbol']} | {http} | {status} |")

    for a in result["attempts"]:
        if a["outcome"] != "ok":
            lines.extend([
                "",
                f"### Raw response (attempt {a['attempt']}, truncated to {OUTPUT_TRUNCATE} B)",
                "```json",
                a["raw"] or "(no body)",
                "```",
                "",
                "### Error",
                "```",
                a["error"] or "unknown",
                "```",
            ])
            break

    syms = SYMBOLS[provider]
    attempted = list(dict.fromkeys(a["symbol"] for a in result["attempts"]))
    lines.extend([
        "",
        "### Resolved symbols",
        f"Primary: {syms[0]}",
        f"Attempted: {', '.join(attempted)}",
        "",
    ])
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> Namespace:
    p = ArgumentParser(description="Provider smoke test")
    p.add_argument("--provider", required=True, choices=list(ENDPOINTS))
    p.add_argument("--format", choices=["text", "markdown"], default="text")
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()
    result = smoke_provider(args.provider)
    output = format_markdown(result) if args.format == "markdown" else format_text(result)
    sys.stdout.write(output)
    sys.stdout.flush()
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
