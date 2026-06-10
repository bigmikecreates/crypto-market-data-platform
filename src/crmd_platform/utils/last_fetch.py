import os
from datetime import datetime, timezone


_MARKER = ".last_fetch"


def mark(base_path: str) -> None:
    now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    os.makedirs(base_path, exist_ok=True)
    with open(os.path.join(base_path, _MARKER), "w") as f:
        f.write(now + "\n")


def read(base_path: str) -> str | None:
    path = os.path.join(base_path, _MARKER)
    try:
        with open(path) as f:
            return f.readline().strip()
    except FileNotFoundError:
        return None
