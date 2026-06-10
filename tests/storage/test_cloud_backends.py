"""Tests for S3 and GCS storage backends."""

from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

# Skip all tests if cloud storage libraries are not installed
s3fs = pytest.importorskip("s3fs", reason="s3fs not installed")
gcsfs = pytest.importorskip("gcsfs", reason="gcsfs not installed")

from crmd_platform.storage.backend import (  # noqa: E402
    GCSBackend,
    S3Backend,
    create_backend,
)


class TestS3Backend:
    """Tests for S3Backend."""

    def test_create_backend_s3_uri(self):
        """Test that create_backend returns S3Backend for s3:// URIs."""
        with patch("s3fs.S3FileSystem"):
            backend = create_backend("s3://bucket/path")
            assert isinstance(backend, S3Backend)

    def test_init_without_s3fs_raises_import_error(self):
        """Test that S3Backend raises ImportError when s3fs is not installed."""
        with patch.dict("sys.modules", {"s3fs": None}):
            with pytest.raises(ImportError, match="s3fs"):
                S3Backend()

    def test_join_path(self):
        """Test that join_path correctly joins S3 paths."""
        with patch("s3fs.S3FileSystem"):
            backend = S3Backend()
            result = backend.join_path("s3://bucket", "path", "to", "file.parquet")
            assert result == "s3://bucket/path/to/file.parquet"

    def test_wrap_path_returns_string(self):
        """Test that wrap_path returns string for S3."""
        with patch("s3fs.S3FileSystem"):
            backend = S3Backend()
            result = backend.wrap_path("s3://bucket/path")
            assert isinstance(result, str)
            assert result == "s3://bucket/path"

    def test_ensure_dir_is_noop(self):
        """Test that ensure_dir is a no-op for S3."""
        with patch("s3fs.S3FileSystem"):
            backend = S3Backend()
            # Should not raise
            backend.ensure_dir("s3://bucket/path")

    def test_exists_delegates_to_filesystem(self):
        """Test that exists delegates to s3fs."""
        with patch("s3fs.S3FileSystem") as mock_fs_class:
            mock_fs = MagicMock()
            mock_fs_class.return_value = mock_fs
            mock_fs.exists.return_value = True

            backend = S3Backend()
            result = backend.exists("s3://bucket/path")

            assert result is True
            mock_fs.exists.assert_called_once_with("s3://bucket/path")

    def test_read_parquet_delegates_to_pyarrow(self):
        """Test that read_parquet delegates to pyarrow with filesystem."""
        with patch("s3fs.S3FileSystem") as mock_fs_class:
            mock_fs = MagicMock()
            mock_fs_class.return_value = mock_fs

            backend = S3Backend()

            with patch("crmd_platform.storage.backend.pq.read_table") as mock_read:
                mock_table = pa.table({"col": [1, 2, 3]})
                mock_read.return_value = mock_table

                result = backend.read_parquet("s3://bucket/path")

                assert result == mock_table
                mock_read.assert_called_once_with(
                    "s3://bucket/path", filesystem=mock_fs
                )

    def test_write_parquet_delegates_to_pyarrow(self):
        """Test that write_parquet delegates to pyarrow with filesystem."""
        with patch("s3fs.S3FileSystem") as mock_fs_class:
            mock_fs = MagicMock()
            mock_fs_class.return_value = mock_fs

            backend = S3Backend()
            table = pa.table({"col": [1, 2, 3]})

            with patch("crmd_platform.storage.backend.pq.write_table") as mock_write:
                backend.write_parquet("s3://bucket/path", table)

                mock_write.assert_called_once_with(
                    table, "s3://bucket/path", filesystem=mock_fs
                )

    def test_glob_delegates_to_filesystem(self):
        """Test that glob delegates to s3fs."""
        with patch("s3fs.S3FileSystem") as mock_fs_class:
            mock_fs = MagicMock()
            mock_fs_class.return_value = mock_fs
            mock_fs.glob.return_value = [
                "s3://bucket/file1.parquet",
                "s3://bucket/file2.parquet",
            ]

            backend = S3Backend()
            result = backend.glob("s3://bucket/**/*.parquet")

            assert result == ["s3://bucket/file1.parquet", "s3://bucket/file2.parquet"]
            mock_fs.glob.assert_called_once_with("s3://bucket/**/*.parquet")


class TestGCSBackend:
    """Tests for GCSBackend."""

    def test_create_backend_gcs_uri(self):
        """Test that create_backend returns GCSBackend for gs:// URIs."""
        with patch("gcsfs.GCSFileSystem"):
            backend = create_backend("gs://bucket/path")
            assert isinstance(backend, GCSBackend)

    def test_init_without_gcsfs_raises_import_error(self):
        """Test that GCSBackend raises ImportError when gcsfs is not installed."""
        with patch.dict("sys.modules", {"gcsfs": None}):
            with pytest.raises(ImportError, match="gcsfs"):
                GCSBackend()

    def test_join_path(self):
        """Test that join_path correctly joins GCS paths."""
        with patch("gcsfs.GCSFileSystem"):
            backend = GCSBackend()
            result = backend.join_path("gs://bucket", "path", "to", "file.parquet")
            assert result == "gs://bucket/path/to/file.parquet"

    def test_wrap_path_returns_string(self):
        """Test that wrap_path returns string for GCS."""
        with patch("gcsfs.GCSFileSystem"):
            backend = GCSBackend()
            result = backend.wrap_path("gs://bucket/path")
            assert isinstance(result, str)
            assert result == "gs://bucket/path"

    def test_ensure_dir_is_noop(self):
        """Test that ensure_dir is a no-op for GCS."""
        with patch("gcsfs.GCSFileSystem"):
            backend = GCSBackend()
            # Should not raise
            backend.ensure_dir("gs://bucket/path")

    def test_exists_delegates_to_filesystem(self):
        """Test that exists delegates to gcsfs."""
        with patch("gcsfs.GCSFileSystem") as mock_fs_class:
            mock_fs = MagicMock()
            mock_fs_class.return_value = mock_fs
            mock_fs.exists.return_value = True

            backend = GCSBackend()
            result = backend.exists("gs://bucket/path")

            assert result is True
            mock_fs.exists.assert_called_once_with("gs://bucket/path")

    def test_read_parquet_delegates_to_pyarrow(self):
        """Test that read_parquet delegates to pyarrow with filesystem."""
        with patch("gcsfs.GCSFileSystem") as mock_fs_class:
            mock_fs = MagicMock()
            mock_fs_class.return_value = mock_fs

            backend = GCSBackend()

            with patch("crmd_platform.storage.backend.pq.read_table") as mock_read:
                mock_table = pa.table({"col": [1, 2, 3]})
                mock_read.return_value = mock_table

                result = backend.read_parquet("gs://bucket/path")

                assert result == mock_table
                mock_read.assert_called_once_with(
                    "gs://bucket/path", filesystem=mock_fs
                )

    def test_write_parquet_delegates_to_pyarrow(self):
        """Test that write_parquet delegates to pyarrow with filesystem."""
        with patch("gcsfs.GCSFileSystem") as mock_fs_class:
            mock_fs = MagicMock()
            mock_fs_class.return_value = mock_fs

            backend = GCSBackend()
            table = pa.table({"col": [1, 2, 3]})

            with patch("crmd_platform.storage.backend.pq.write_table") as mock_write:
                backend.write_parquet("gs://bucket/path", table)

                mock_write.assert_called_once_with(
                    table, "gs://bucket/path", filesystem=mock_fs
                )

    def test_glob_delegates_to_filesystem(self):
        """Test that glob delegates to gcsfs."""
        with patch("gcsfs.GCSFileSystem") as mock_fs_class:
            mock_fs = MagicMock()
            mock_fs_class.return_value = mock_fs
            mock_fs.glob.return_value = [
                "gs://bucket/file1.parquet",
                "gs://bucket/file2.parquet",
            ]

            backend = GCSBackend()
            result = backend.glob("gs://bucket/**/*.parquet")

            assert result == ["gs://bucket/file1.parquet", "gs://bucket/file2.parquet"]
            mock_fs.glob.assert_called_once_with("gs://bucket/**/*.parquet")
