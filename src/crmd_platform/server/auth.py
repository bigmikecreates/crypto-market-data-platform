import secrets

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    request: Request,
    api_key: str | None = Security(_API_KEY_HEADER),
) -> None:
    """Enforce API key authentication when CRMD_API_KEY is configured.

    When no key is configured on the server (dev mode), all requests are allowed.
    When a key is configured, every request must supply it in the ``X-API-Key``
    header. ``secrets.compare_digest`` prevents timing-based key enumeration.
    """
    expected: str | None = request.app.state.api_key
    if expected is None:
        return  # dev mode — open access
    if not api_key or not secrets.compare_digest(api_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
