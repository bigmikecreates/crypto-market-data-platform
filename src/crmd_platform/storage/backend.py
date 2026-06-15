"""Cloud-agnostic storage backend abstraction.

This module provides a unified interface for reading and writing Parquet files
across different storage systems (local filesystem, Azure Blob, S3, GCS).
"""

import logging
import os
import random
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

import pyarrow as pa
import pyarrow.parquet as pq

LOG = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends.

    Implementations must provide methods for reading, writing, and managing
    Parquet files with optional concurrency control.
    """

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a file exists at the given path."""
        pass

    @abstractmethod
    def read_parquet(self, path: str) -> pa.Table:
        """Read a Parquet file into a PyArrow table."""
        pass

    @abstractmethod
    def write_parquet(self, path: str, table: pa.Table) -> None:
        """Write a PyArrow table to a Parquet file."""
        pass

    @abstractmethod
    def write_parquet_with_lease(
        self,
        path: str,
        table: pa.Table,
        merge_fn: Callable[[pa.Table], pa.Table],
    ) -> None:
        """Write a table with concurrency control.

        Args:
            path: Target file path
            table: Table to write
            merge_fn: Function that takes existing table (or None) and returns merged table
        """
        pass

    @abstractmethod
    def glob(self, pattern: str) -> list[str]:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "data/**/*.parquet")

        Returns:
            List of matching file paths
        """
        pass

    @abstractmethod
    def join_path(self, *parts: str) -> str:
        """Join path components safely for this backend.

        Cloud backends must avoid pathlib.Path which normalizes
        schemes like az:// to az:/
        """
        pass

    @abstractmethod
    def ensure_dir(self, path: str) -> None:
        """Ensure the directory for a file path exists."""
        pass

    @abstractmethod
    def wrap_path(self, path: str) -> Path | str:
        """Wrap a path string in the appropriate type for this backend.

        LocalStorageBackend returns Path objects.
        Cloud backends return strings (since paths may be URIs).
        """
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def read_parquet(self, path: str) -> pa.Table:
        return pq.read_table(path)

    def write_parquet(self, path: str, table: pa.Table) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path)

    def write_parquet_with_lease(
        self,
        path: str,
        table: pa.Table,
        merge_fn: Callable[[pa.Table], pa.Table],
    ) -> None:
        """Write with no-op lease for local storage.

        Local storage doesn't need concurrency control since each symbol
        maps to a different partition file.
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        if Path(path).exists():
            existing = pq.read_table(path)
            table = merge_fn(existing)

        pq.write_table(table, path)

    def glob(self, pattern: str) -> list[str]:
        """Find files matching a glob pattern.

        For local storage, we use pathlib's rglob on the base directory.
        """
        # Extract base directory and file pattern
        # Pattern format: "base_dir/**/*.parquet"
        parts = pattern.split("/**/", 1)
        if len(parts) == 2:
            base_dir = parts[0]
            file_pattern = parts[1]
        else:
            base_dir = pattern.rsplit("/", 1)[0] if "/" in pattern else "."
            file_pattern = pattern.rsplit("/", 1)[1] if "/" in pattern else pattern

        base_path = Path(base_dir)
        if not base_path.exists():
            return []

        return sorted(str(p) for p in base_path.rglob(file_pattern))

    def join_path(self, *parts: str) -> str:
        return str(Path(*parts))

    def ensure_dir(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def wrap_path(self, path: str) -> Path:
        """Wrap a path string in a Path object for local storage."""
        return Path(path)


class AzureBlobBackend(StorageBackend):
    """Azure Blob Storage backend using adlfs.

    Supports three authentication methods (checked in order):
    1. Connection string — via ``connection_string`` param or ``AZURE_STORAGE_CONNECTION_STRING`` env
    2. Account name + access key — via ``AZURE_STORAGE_ACCOUNT`` + ``AZURE_STORAGE_KEY`` env vars
    3. Managed identity — via ``AZURE_STORAGE_ACCOUNT`` env var only (uses ``DefaultAzureCredential``)
    """

    def __init__(self, connection_string: str | None = None):
        """Initialize Azure Blob backend.

        Args:
            connection_string: Azure Storage connection string.
                             If None, reads from AZURE_STORAGE_CONNECTION_STRING env var,
                             then falls back to AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_KEY,
                             then AZURE_STORAGE_ACCOUNT (managed identity).
        """
        try:
            import adlfs
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient
        except ImportError:
            raise ImportError(
                "Azure Blob Storage requires adlfs and azure-identity. "
                "Install with: pip install 'crmd-platform[azure]'"
            )

        self._connection_string = connection_string or os.environ.get(
            "AZURE_STORAGE_CONNECTION_STRING"
        )
        self._account_name: str | None = None
        self._account_key: str | None = None
        self._use_managed_identity = False

        if self._connection_string:
            self._auth_method = "connection_string"
            self._fs = adlfs.AzureBlobFileSystem(
                connection_string=self._connection_string
            )
            self._service_client = BlobServiceClient.from_connection_string(
                self._connection_string
            )
        else:
            self._account_name = os.environ.get("AZURE_STORAGE_ACCOUNT")
            if not self._account_name:
                raise ValueError(
                    "Azure credentials required. "
                    "Set AZURE_STORAGE_CONNECTION_STRING, or "
                    "AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_KEY, or "
                    "AZURE_STORAGE_ACCOUNT (for managed identity)."
                )

            self._account_key = os.environ.get("AZURE_STORAGE_KEY")
            account_url = f"https://{self._account_name}.blob.core.windows.net"

            if self._account_key:
                self._auth_method = "account_key"
                self._fs = adlfs.AzureBlobFileSystem(
                    account_name=self._account_name,
                    account_key=self._account_key,
                )
                self._service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=self._account_key,
                )
            else:
                self._auth_method = "managed_identity"
                self._use_managed_identity = True
                self._fs = adlfs.AzureBlobFileSystem(
                    account_name=self._account_name,
                )
                self._service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=DefaultAzureCredential(),
                )

    def duckdb_setup_sql(self) -> list[str]:
        """Return SQL statements to configure DuckDB's azure extension."""
        if self._auth_method == "connection_string":
            return [
                f"SET azure_storage_connection_string = '{self._connection_string}';"
            ]
        if self._auth_method == "account_key":
            return [
                f"SET azure_storage_account_name = '{self._account_name}';",
                f"SET azure_storage_account_key = '{self._account_key}';",
            ]
        return []

    def _get_blob_client(self, blob_path: str):
        """Get Azure Blob client for a path."""
        # blob_path format: "container/path/to/file.parquet"
        parts = blob_path.split("/", 1)
        container = parts[0]
        blob = parts[1] if len(parts) > 1 else ""
        return self._service_client.get_blob_client(container=container, blob=blob)

    def exists(self, path: str) -> bool:
        return self._fs.exists(path)

    def read_parquet(self, path: str) -> pa.Table:
        return pq.read_table(path, filesystem=self._fs)

    def write_parquet(self, path: str, table: pa.Table) -> None:
        pq.write_table(table, path, filesystem=self._fs)

    def write_parquet_with_lease(
        self,
        path: str,
        table: pa.Table,
        merge_fn: Callable[[pa.Table], pa.Table],
    ) -> None:
        """Write with Azure Blob lease-based concurrency control.

        Uses a 30-second lease to serialize concurrent writes to the same blob.
        """
        from azure.core.exceptions import HttpResponseError

        blob_client = self._get_blob_client(path)
        max_attempts = 6

        def serialize_table(t: pa.Table) -> bytes:
            """Serialize table to Parquet bytes."""
            sink = pa.BufferOutputStream()
            pq.write_table(t, sink)
            return sink.getvalue().to_pybytes()

        def backoff(attempt: int) -> None:
            time.sleep(min(0.5 * (2**attempt), 8.0) + random.uniform(0, 0.5))

        for attempt in range(max_attempts):
            if not self._fs.exists(path):
                # No blob yet — write conditionally so a racing creator triggers 409
                try:
                    blob_client.upload_blob(serialize_table(table), overwrite=False)
                    return
                except HttpResponseError as e:
                    if e.status_code != 409:
                        raise
                    # Another worker created the blob; fall through to lease path
            else:
                # Blob exists — acquire exclusive lease before read-merge-write
                try:
                    lease = blob_client.acquire_lease(lease_duration=30)
                except HttpResponseError as e:
                    if e.status_code != 409:
                        raise
                    backoff(attempt)
                    continue

                try:
                    existing = pq.read_table(path, filesystem=self._fs)
                    merged = merge_fn(existing)
                    blob_client.upload_blob(
                        serialize_table(merged), overwrite=True, lease=lease
                    )
                    return
                finally:
                    try:
                        lease.release()
                    except Exception:
                        LOG.warning("Failed to release Azure lease", exc_info=True)

            backoff(attempt)

        raise RuntimeError(
            f"Could not write to '{path}' after {max_attempts} attempts — "
            "lease contention or transient Azure error"
        )

    def glob(self, pattern: str) -> list[str]:
        """Find files matching a glob pattern in Azure Blob Storage.

        Uses adlfs glob which supports ** wildcards.
        """
        return sorted(self._fs.glob(pattern))

    def join_path(self, *parts: str) -> str:
        """Join path components without pathlib normalization.

        Azure URIs like az://container/path must not be normalized to az:/container/path
        """
        return "/".join(p.rstrip("/") for p in parts if p)

    def ensure_dir(self, path: str) -> None:
        """No-op for Azure Blob Storage (directories don't exist)."""
        pass

    def wrap_path(self, path: str) -> str:
        """Return path as string for cloud storage (paths may be URIs)."""
        return path


class S3Backend(StorageBackend):
    """AWS S3 storage backend using s3fs."""

    def __init__(
        self,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str | None = None,
    ):
        """Initialize S3 backend.

        Args:
            aws_access_key_id: AWS access key ID. If None, reads from AWS_ACCESS_KEY_ID env var.
            aws_secret_access_key: AWS secret access key. If None, reads from AWS_SECRET_ACCESS_KEY env var.
            region_name: AWS region. If None, reads from AWS_DEFAULT_REGION env var or uses default.
        """
        try:
            import s3fs
        except ImportError:
            raise ImportError(
                "S3 storage requires s3fs. "
                "Install with: pip install 'crmd-platform[s3]'"
            )

        self._access_key = aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")
        self._secret_key = aws_secret_access_key or os.environ.get(
            "AWS_SECRET_ACCESS_KEY"
        )
        self._region = region_name or os.environ.get("AWS_DEFAULT_REGION")

        # s3fs will use IAM roles or env vars if credentials not provided
        self._fs = s3fs.S3FileSystem(
            key=self._access_key,
            secret=self._secret_key,
            client_kwargs={"region_name": self._region} if self._region else None,
        )

    def exists(self, path: str) -> bool:
        return self._fs.exists(path)

    def read_parquet(self, path: str) -> pa.Table:
        return pq.read_table(path, filesystem=self._fs)

    def write_parquet(self, path: str, table: pa.Table) -> None:
        pq.write_table(table, path, filesystem=self._fs)

    def write_parquet_with_lease(
        self,
        path: str,
        table: pa.Table,
        merge_fn: Callable[[pa.Table], pa.Table],
    ) -> None:
        """Write with read-merge-write pattern for S3.

        S3 doesn't have Azure-style leases, but we can use conditional PUT
        operations. For simplicity, we use a read-merge-write pattern similar
        to local storage. For production use with high concurrency, consider
        using S3's conditional PUT with ETags or DynamoDB locking.
        """
        if self._fs.exists(path):
            existing = pq.read_table(path, filesystem=self._fs)
            table = merge_fn(existing)

        pq.write_table(table, path, filesystem=self._fs)

    def glob(self, pattern: str) -> list[str]:
        """Find files matching a glob pattern in S3.

        Uses s3fs glob which supports ** wildcards.
        """
        return sorted(self._fs.glob(pattern))

    def join_path(self, *parts: str) -> str:
        """Join path components without pathlib normalization.

        S3 URIs like s3://bucket/path must not be normalized to s3:/bucket/path
        """
        return "/".join(p.rstrip("/") for p in parts if p)

    def ensure_dir(self, path: str) -> None:
        """No-op for S3 (directories don't exist)."""
        pass

    def wrap_path(self, path: str) -> str:
        """Return path as string for cloud storage (paths may be URIs)."""
        return path


class GCSBackend(StorageBackend):
    """Google Cloud Storage backend using gcsfs."""

    def __init__(
        self,
        project: str | None = None,
        token: str | None = None,
    ):
        """Initialize GCS backend.

        Args:
            project: GCP project ID. If None, reads from GOOGLE_CLOUD_PROJECT env var.
            token: Authentication token. If None, uses default credentials.
        """
        try:
            import gcsfs
        except ImportError:
            raise ImportError(
                "GCS storage requires gcsfs. "
                "Install with: pip install 'crmd-platform[gcs]'"
            )

        self._project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self._token = token  # gcsfs will use default credentials if None

        self._fs = gcsfs.GCSFileSystem(project=self._project, token=self._token)

    def exists(self, path: str) -> bool:
        return self._fs.exists(path)

    def read_parquet(self, path: str) -> pa.Table:
        return pq.read_table(path, filesystem=self._fs)

    def write_parquet(self, path: str, table: pa.Table) -> None:
        pq.write_table(table, path, filesystem=self._fs)

    def write_parquet_with_lease(
        self,
        path: str,
        table: pa.Table,
        merge_fn: Callable[[pa.Table], pa.Table],
    ) -> None:
        """Write with read-merge-write pattern for GCS.

        GCS supports object versioning and conditional operations, but for
        simplicity we use a read-merge-write pattern similar to local storage.
        For production use with high concurrency, consider using GCS's
        conditional operations or Cloud Storage locking.
        """
        if self._fs.exists(path):
            existing = pq.read_table(path, filesystem=self._fs)
            table = merge_fn(existing)

        pq.write_table(table, path, filesystem=self._fs)

    def glob(self, pattern: str) -> list[str]:
        """Find files matching a glob pattern in GCS.

        Uses gcsfs glob which supports ** wildcards.
        """
        return sorted(self._fs.glob(pattern))

    def join_path(self, *parts: str) -> str:
        """Join path components without pathlib normalization.

        GCS URIs like gs://bucket/path must not be normalized to gs:/bucket/path
        """
        return "/".join(p.rstrip("/") for p in parts if p)

    def ensure_dir(self, path: str) -> None:
        """No-op for GCS (directories don't exist)."""
        pass

    def wrap_path(self, path: str) -> str:
        """Return path as string for cloud storage (paths may be URIs)."""
        return path


def create_backend(base_path: str) -> StorageBackend:
    """Factory function to create appropriate storage backend.

    Args:
        base_path: Storage path (local path or cloud URI)

    Returns:
        StorageBackend instance

    Examples:
        >>> backend = create_backend("data")  # Local
        >>> backend = create_backend("az://container/path")  # Azure
        >>> backend = create_backend("s3://bucket/path")  # S3
        >>> backend = create_backend("gs://bucket/path")  # GCS
    """
    if base_path.startswith(("az://", "abfs://")):
        return AzureBlobBackend()
    elif base_path.startswith("s3://"):
        return S3Backend()
    elif base_path.startswith("gs://"):
        return GCSBackend()
    else:
        return LocalStorageBackend()
