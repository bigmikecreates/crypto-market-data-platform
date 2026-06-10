import os
from datetime import datetime, timezone


_MARKER = ".last_fetch"


def _is_cloud_path(base_path: str) -> bool:
    """Check if base_path is a cloud storage URI."""
    return base_path.startswith(("az://", "abfs://", "s3://", "gs://"))


def mark(base_path: str) -> None:
    """Mark the last fetch time for a storage path.

    For local paths, writes a marker file.
    For cloud paths, this is a no-op (cloud storage doesn't support simple file writes).
    """
    if _is_cloud_path(base_path):
        # Cloud storage doesn't support simple marker files
        # The last fetch time is tracked by the data itself (latest timestamp in storage)
        return

    now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    os.makedirs(base_path, exist_ok=True)
    with open(os.path.join(base_path, _MARKER), "w") as f:
        f.write(now + "\n")


def read(base_path: str) -> str | None:
    """Read the last fetch time for a storage path.

    For local paths, reads the marker file.
    For cloud paths, returns None (not tracked via marker file).
    """
    if _is_cloud_path(base_path):
        # Cloud storage doesn't use marker files
        return None

    path = os.path.join(base_path, _MARKER)
    try:
        with open(path) as f:
            return f.readline().strip()
    except FileNotFoundError:
        return None
