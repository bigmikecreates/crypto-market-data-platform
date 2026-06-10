"""Tests for StorageBackend abstraction."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from crmd_platform.storage.backend import (
    LocalStorageBackend,
    create_backend,
)


class TestCreateBackend:
    def test_local_path_returns_local_backend(self):
        backend = create_backend("data")
        assert isinstance(backend, LocalStorageBackend)

    def test_absolute_path_returns_local_backend(self):
        backend = create_backend("/tmp/data")
        assert isinstance(backend, LocalStorageBackend)

    def test_azure_uri_raises_import_error_when_adlfs_missing(self):
        # Mock adlfs import to raise ImportError
        with patch.dict("sys.modules", {"adlfs": None}):
            with pytest.raises(ImportError, match="adlfs"):
                create_backend("az://container/path")

    def test_s3_uri_raises_import_error_when_s3fs_missing(self):
        """Test that S3Backend raises ImportError when s3fs is not installed."""
        with patch.dict("sys.modules", {"s3fs": None}):
            with pytest.raises(ImportError, match="s3fs"):
                create_backend("s3://bucket/path")

    def test_gcs_uri_raises_import_error_when_gcsfs_missing(self):
        """Test that GCSBackend raises ImportError when gcsfs is not installed."""
        with patch.dict("sys.modules", {"gcsfs": None}):
            with pytest.raises(ImportError, match="gcsfs"):
                create_backend("gs://bucket/path")


class TestLocalStorageBackend:
    def test_exists_returns_false_for_missing_file(self):
        backend = LocalStorageBackend()
        assert not backend.exists("/nonexistent/file.parquet")

    def test_exists_returns_true_for_existing_file(self):
        backend = LocalStorageBackend()
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            # Write a minimal parquet file
            table = pa.table({"col": [1, 2, 3]})
            pq.write_table(table, f.name)
            try:
                assert backend.exists(f.name)
            finally:
                Path(f.name).unlink()

    def test_join_path_joins_components(self):
        backend = LocalStorageBackend()
        result = backend.join_path("data", "exchange", "symbol", "file.parquet")
        assert result == str(Path("data/exchange/symbol/file.parquet"))

    def test_ensure_dir_creates_parent_directories(self):
        backend = LocalStorageBackend()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "level1" / "level2" / "file.parquet"
            backend.ensure_dir(str(test_path))
            assert test_path.parent.exists()

    def test_glob_finds_matching_files(self):
        backend = LocalStorageBackend()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test files
            (Path(tmpdir) / "file1.parquet").touch()
            (Path(tmpdir) / "file2.parquet").touch()
            (Path(tmpdir) / "file3.txt").touch()

            results = backend.glob(f"{tmpdir}/**/*.parquet")
            assert len(results) == 2
            assert all(r.endswith(".parquet") for r in results)
