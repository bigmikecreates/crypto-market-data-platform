from pathlib import Path

import pyarrow.parquet as pq
from typer.testing import CliRunner

from crypto_market_data_platform.cli.main import app

runner = CliRunner()


class TestFetchCommand:
    def test_fetch_with_fake_provider_creates_parquet(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "fetch",
                "--symbol",
                "BTC/USDT",
                "--timeframe",
                "1h",
                "--start",
                "2026-05-27",
                "--end",
                "2026-05-28",
                "--provider",
                "fake",
                "--output",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "Wrote 1 candle(s)" in result.stdout

        parquet_file = tmp_path / "fake" / "BTC/USDT" / "1h" / "2026-05-27.parquet"
        assert parquet_file.exists(), f"Expected {parquet_file} to exist"

    def test_fetch_unknown_provider_exits_with_error(self) -> None:
        result = runner.invoke(
            app,
            [
                "fetch",
                "--symbol",
                "BTC/USDT",
                "--timeframe",
                "1h",
                "--start",
                "2026-05-27",
                "--end",
                "2026-05-28",
                "--provider",
                "kraken",
            ],
        )
        assert result.exit_code == 1
        assert "Unknown provider" in result.stderr

    def test_fetch_default_provider_is_fake(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "fetch",
                "--symbol",
                "ETH/USDT",
                "--timeframe",
                "1d",
                "--start",
                "2026-05-27",
                "--end",
                "2026-05-28",
                "--output",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "Wrote 1 candle(s)" in result.stdout

    def test_fetch_funding_rate_creates_parquet(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "fetch",
                "--mdt",
                "funding-rate",
                "--symbol",
                "BTC/USDT",
                "--start",
                "2026-05-27",
                "--end",
                "2026-05-28",
                "--output",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "Wrote 1 funding rate(s)" in result.stdout

        parquet_file = (
            tmp_path / "fake" / "BTC/USDT" / "funding_rate" / "2026-05-27.parquet"
        )
        assert parquet_file.exists(), f"Expected {parquet_file} to exist"
        table = pq.read_table(str(parquet_file))
        assert table.num_rows == 1
        assert table.schema.names == [
            "exchange",
            "symbol",
            "timestamp",
            "rate",
            "predicted_rate",
            "next_funding_time",
            "source",
        ]
