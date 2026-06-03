from __future__ import annotations

import socket
import time
from multiprocessing import Process
from pathlib import Path

import httpx

from crmd_platform.server.config import ServerConfig

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PORT: int = ServerConfig().port  # slots=True prevents class-level access


# ── port-alignment tests ───────────────────────────────────────────


def test_backend_port_matches_frontend_fallback() -> None:
    """Frontend api.ts fallback URL must use the same port as ServerConfig."""
    api_ts = _PROJECT_ROOT / "frontend" / "lib" / "api.ts"
    content = api_ts.read_text()
    expected = f"localhost:{_DEFAULT_PORT}"
    assert expected in content, (
        f"Frontend api.ts fallback doesn't match backend default port {_DEFAULT_PORT}. "
        f"Expected 'localhost:{_DEFAULT_PORT}'."
    )


def test_backend_port_matches_frontend_env_example() -> None:
    """Frontend .env.local.example must use the same port as ServerConfig."""
    env_example = _PROJECT_ROOT / "frontend" / ".env.local.example"
    content = env_example.read_text()
    expected = f"localhost:{_DEFAULT_PORT}"
    assert expected in content, (
        f"Frontend .env.local.example doesn't match backend default port "
        f"{_DEFAULT_PORT}. Expected 'localhost:{_DEFAULT_PORT}'."
    )


# ── server startup test ────────────────────────────────────────────


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_server(base_path: str, port: int) -> None:
    from crmd_platform.server import create_app
    import uvicorn

    config = ServerConfig(base_path=base_path, port=port)
    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="error")


def test_server_starts_and_responds(tmp_path: Path) -> None:
    """Spawn uvicorn in a subprocess and verify it serves /health."""
    port = _free_port()
    proc = Process(target=_run_server, args=(str(tmp_path), port), daemon=True)
    proc.start()

    try:
        for attempt in range(10):
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
                assert resp.status_code == 200
                assert resp.json() == {"status": "ok"}
                return
            except (httpx.ConnectError, httpx.RemoteProtocolError):
                if attempt == 9:
                    raise
                time.sleep(0.5)
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
