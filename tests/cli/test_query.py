from pathlib import Path

from typer.testing import CliRunner

from crypto_market_data_platform.cli.main import app
from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate
from crypto_market_data_platform.query import DuckDBQueryService
from crypto_market_data_platform.storage.parquet_writer import (
    write_candles,
    write_funding_rates,
)

runner = CliRunner()


def _write_candle_fixtures(base: str) -> None:
    candles = [
        Candle(
            exchange="ex_a",
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp="2026-05-27T00:00:00",
            open="100",
            high="110",
            low="90",
            close="105",
            volume="10",
            source="test",
        ),
        Candle(
            exchange="ex_a",
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp="2026-05-28T00:00:00",
            open="101",
            high="111",
            low="91",
            close="106",
            volume="11",
            source="test",
        ),
        Candle(
            exchange="ex_a",
            symbol="ETH/USDT",
            timeframe="1h",
            timestamp="2026-05-27T00:00:00",
            open="200",
            high="210",
            low="190",
            close="205",
            volume="20",
            source="test",
        ),
    ]
    write_candles(candles, base_path=base)


def _write_funding_fixtures(base: str) -> None:
    rates = [
        FundingRate(
            exchange="ex_a",
            symbol="PI_XBTUSD",
            timestamp="2026-05-27T12:00:00",
            rate="0.0001",
            predicted_rate="0.0002",
            next_funding_time="2026-05-27T16:00:00",
            source="test",
        ),
        FundingRate(
            exchange="ex_a",
            symbol="PI_ETHUSD",
            timestamp="2026-05-27T12:00:00",
            rate="-0.0001",
            predicted_rate="0.0000",
            next_funding_time="2026-05-27T16:00:00",
            source="test",
        ),
    ]
    write_funding_rates(rates, base_path=base)


# ── DuckDBQueryService unit tests ────────────────────────────────


class TestDuckDBQueryService:
    def setup_method(self) -> None:
        self.svc = DuckDBQueryService()

    def test_list_datasets_empty(self, tmp_path: Path) -> None:
        datasets = self.svc.list_datasets(str(tmp_path))
        assert datasets == {}

    def test_list_datasets_both_types(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        _write_funding_fixtures(str(tmp_path))
        datasets = self.svc.list_datasets(str(tmp_path))
        assert "candle" in datasets
        assert "funding_rate" in datasets
        assert "ex_a/BTC/USDT/1h" in datasets["candle"]
        assert "ex_a/ETH/USDT/1h" in datasets["candle"]
        assert "ex_a/PI_XBTUSD/funding_rate" in datasets["funding_rate"]

    def test_get_candles_all(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        rows = self.svc.get_candles(str(tmp_path), limit=10)
        assert len(rows) == 3
        assert all(isinstance(r, Candle) for r in rows)

    def test_get_candles_filter_exchange(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        rows = self.svc.get_candles(str(tmp_path), exchange="ex_a", limit=10)
        assert len(rows) == 3

    def test_get_candles_filter_symbol(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        rows = self.svc.get_candles(str(tmp_path), symbol="BTC/USDT", limit=10)
        assert len(rows) == 2

    def test_get_candles_filter_timeframe(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        rows = self.svc.get_candles(str(tmp_path), timeframe="1h", limit=10)
        assert len(rows) == 3

    def test_get_candles_filter_start(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        rows = self.svc.get_candles(str(tmp_path), start="2026-05-28", limit=10)
        assert len(rows) == 1
        assert rows[0].open == "101.0000000000"

    def test_get_candles_filter_end(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        rows = self.svc.get_candles(str(tmp_path), end="2026-05-28", limit=10)
        assert len(rows) == 2

    def test_get_candles_no_match_returns_empty(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        rows = self.svc.get_candles(str(tmp_path), exchange="nonexistent")
        assert rows == []

    def test_get_funding_rates(self, tmp_path: Path) -> None:
        _write_funding_fixtures(str(tmp_path))
        rows = self.svc.get_funding_rates(str(tmp_path), limit=10)
        assert len(rows) == 2
        assert all(isinstance(r, FundingRate) for r in rows)

    def test_get_funding_rates_filter_symbol(self, tmp_path: Path) -> None:
        _write_funding_fixtures(str(tmp_path))
        rows = self.svc.get_funding_rates(str(tmp_path), symbol="PI_XBTUSD", limit=10)
        assert len(rows) == 1
        assert rows[0].rate == "0.0001000000"

    def test_get_summary(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        _write_funding_fixtures(str(tmp_path))
        summary = self.svc.get_summary(str(tmp_path))
        assert len(summary) == 4  # 2 candle datasets + 2 funding datasets
        types = {r["type"] for r in summary}
        assert types == {"candle", "funding_rate"}

    def test_raw_sql(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        rows = self.svc.raw_sql(
            f"SELECT open, close FROM read_parquet('{tmp_path}/ex_a/BTC/USDT/1h/*.parquet') WHERE open = '100'"
        )
        assert len(rows) == 1
        assert rows[0]["open"] == "100.0000000000"
        assert rows[0]["close"] == "105.0000000000"

    def test_raw_sql_no_results(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        rows = self.svc.raw_sql("SELECT 1 AS a WHERE 1 = 0")
        assert rows == []


# ── CLI integration tests ────────────────────────────────────────


class TestDatasetsCommand:
    def test_datasets_shows_summary(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        _write_funding_fixtures(str(tmp_path))
        result = runner.invoke(app, ["datasets", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "candle" in result.stdout
        assert "funding_rate" in result.stdout
        assert "rows=" in result.stdout

    def test_datasets_no_files(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["datasets", "--path", str(tmp_path)])
        assert result.exit_code == 1
        assert "No parquet files found" in result.stdout


class TestQueryOhlcvCommand:
    def test_query_ohlcv_all(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        result = runner.invoke(
            app, ["query", "ohlcv", "--path", str(tmp_path), "--limit", "10"]
        )
        assert result.exit_code == 0
        assert "exchange" in result.stdout
        assert "ex_a" in result.stdout
        assert "(3 row(s))" in result.stdout

    def test_query_ohlcv_filter_symbol(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        result = runner.invoke(
            app,
            [
                "query",
                "ohlcv",
                "--path",
                str(tmp_path),
                "--symbol",
                "BTC/USDT",
                "--limit",
                "10",
            ],
        )
        assert result.exit_code == 0
        assert "(2 row(s))" in result.stdout

    def test_query_ohlcv_no_match(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        result = runner.invoke(
            app,
            ["query", "ohlcv", "--path", str(tmp_path), "--exchange", "nonexistent"],
        )
        assert result.exit_code == 0
        assert "(no results)" in result.stdout


class TestQueryFundingRateCommand:
    def test_funding_rate_all(self, tmp_path: Path) -> None:
        _write_funding_fixtures(str(tmp_path))
        result = runner.invoke(
            app, ["query", "funding-rate", "--path", str(tmp_path), "--limit", "10"]
        )
        assert result.exit_code == 0
        assert "exchange" in result.stdout
        assert "ex_a" in result.stdout
        assert "(2 row(s))" in result.stdout

    def test_funding_rate_no_match(self, tmp_path: Path) -> None:
        _write_funding_fixtures(str(tmp_path))
        result = runner.invoke(
            app,
            [
                "query",
                "funding-rate",
                "--path",
                str(tmp_path),
                "--symbol",
                "NONEXISTENT",
            ],
        )
        assert result.exit_code == 0
        assert "(no results)" in result.stdout


class TestQuerySqlCommand:
    def test_raw_sql(self, tmp_path: Path) -> None:
        _write_candle_fixtures(str(tmp_path))
        glob_path = f"{tmp_path}/ex_a/BTC/USDT/1h/*.parquet"
        result = runner.invoke(
            app,
            [
                "query",
                "sql",
                f"SELECT open FROM read_parquet('{glob_path}') WHERE open = '100'",
                "--path",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "open" in result.stdout
        assert "100.0000000000" in result.stdout
        assert "(1 row(s))" in result.stdout
