import re
import sys
import urllib.error
import urllib.request
from argparse import ArgumentParser, Namespace
from datetime import datetime, timezone
from typing import Any

from scripts.smoke.config import (
    API_VERSIONS,
    ENDPOINTS,
    OUTPUT_TRUNCATE,
    SYMBOLS,
    USER_AGENT,
)
from scripts.smoke.parsers import parse_via_provider

AttemptResult = dict[str, Any]


def _attempt(provider: str, symbol: str, attempt_num: int) -> AttemptResult:
    now = datetime.now(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0)
    start = end.replace(hour=end.hour - 1)

    url = ENDPOINTS[provider](symbol, start, end)
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
            parse_err = parse_via_provider(provider, raw)
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

    return {
        "provider": provider,
        "passed": failure_count < 2,
        "configured_version": configured_version,
        "version_info": version_info,
        "attempts": attempts,
        "success_count": success_count,
        "failure_count": failure_count,
    }


def _attempt_row(a: AttemptResult) -> str:
    sym = a["symbol"]
    if a["outcome"] == "ok":
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
        "## Provider smoke test failure",
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
