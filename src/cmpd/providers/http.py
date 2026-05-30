import json
from typing import Any

import urllib3

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) crypto-market-data-platform/1.0"
_HEADERS = {"Accept": "application/json", "User-Agent": _USER_AGENT}

# Module-level pool: one TCP connection reused per host across all fetches.
_http = urllib3.PoolManager(maxconnections=10, headers=_HEADERS)


def fetch_json(url: str, exchange: str, timeout: int = 30) -> Any:
    try:
        resp = _http.request(
            "GET",
            url,
            timeout=urllib3.Timeout(connect=10, read=timeout),
        )
    except urllib3.exceptions.MaxRetryError as e:
        raise RuntimeError(f"{exchange} network error: {e.reason}") from None
    except urllib3.exceptions.TimeoutError:
        raise RuntimeError(f"{exchange} request timed out after {timeout}s") from None

    if resp.status >= 400:
        try:
            err_info = json.loads(resp.data.decode())
        except json.JSONDecodeError:
            err_info = resp.data.decode()
        raise RuntimeError(f"{exchange} API error (HTTP {resp.status}): {err_info}")

    return json.loads(resp.data.decode())
