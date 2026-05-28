from fastapi.testclient import TestClient
from pytest import fixture

from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate
from crypto_market_data_platform.server import create_app
from crypto_market_data_platform.server.config import ServerConfig
from crypto_market_data_platform.storage.parquet_writer import (
    write_candles,
    write_funding_rates,
)


@fixture
def client(tmp_path):
    cfg = ServerConfig(base_path=str(tmp_path))
    return TestClient(create_app(cfg))


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
    ]
    write_funding_rates(rates, base_path=base)


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestDatasets:
    def test_list_datasets_empty(self, client, tmp_path):
        resp = client.get(f"/datasets?path={tmp_path}")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_list_datasets_with_data(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        _write_funding_fixtures(str(tmp_path))
        resp = client.get(f"/datasets?path={tmp_path}")
        assert resp.status_code == 200
        data = resp.json()
        assert "ex_a/BTC/USDT/1h" in data["candle"]
        assert "ex_a/PI_XBTUSD/funding_rate" in data["funding_rate"]


class TestCandles:
    def test_get_candles_all(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get(f"/candles?path={tmp_path}")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        assert rows[0]["symbol"] == "BTC/USDT"

    def test_get_candles_filter_symbol(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get(f"/candles?path={tmp_path}&symbol=BTC/USDT")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2

    def test_get_candles_no_match(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get(f"/candles?path={tmp_path}&symbol=DOGE/USDT")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_candles_limit_too_high(self, client, tmp_path):
        resp = client.get(f"/candles?path={tmp_path}&limit=99999")
        assert resp.status_code == 422


class TestFundingRates:
    def test_get_funding_rates_all(self, client, tmp_path):
        _write_funding_fixtures(str(tmp_path))
        resp = client.get(f"/funding-rates?path={tmp_path}")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["symbol"] == "PI_XBTUSD"

    def test_get_funding_rates_no_match(self, client, tmp_path):
        _write_funding_fixtures(str(tmp_path))
        resp = client.get(f"/funding-rates?path={tmp_path}&symbol=DOGE")
        assert resp.status_code == 200
        assert resp.json() == []


class TestRawQuery:
    def test_raw_query(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.post(
            "/query",
            json={
                "sql": f"SELECT count(*) AS cnt FROM read_parquet('{tmp_path}/**/*.parquet')",
                "path": str(tmp_path),
            },
        )
        assert resp.status_code == 200
        rows = resp.json()
        assert rows[0]["cnt"] == 2

    def test_raw_query_invalid_body(self, client):
        resp = client.post("/query", json={})
        assert resp.status_code == 422


class TestSummary:
    def test_summary_empty(self, client, tmp_path):
        resp = client.get(f"/summary?path={tmp_path}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_summary_with_data(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        _write_funding_fixtures(str(tmp_path))
        resp = client.get(f"/summary?path={tmp_path}")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        types = {r["type"] for r in rows}
        assert types == {"candle", "funding_rate"}
        for r in rows:
            assert r["files"] >= 1
            assert r["rows"] >= 1


class TestErrorHandling:
    def test_internal_error_returns_500_json(self, client):
        class FailingQueryService:
            def list_datasets(self, base_path="data"):
                raise RuntimeError("boom")

            def get_candles(self, **kw):
                raise RuntimeError("boom")

            def get_funding_rates(self, **kw):
                raise RuntimeError("boom")

            def get_summary(self, base_path="data"):
                raise RuntimeError("boom")

            def raw_sql(self, sql, base_path="data"):
                raise RuntimeError("boom")

        from crypto_market_data_platform.server.config import ServerConfig

        cfg = ServerConfig(
            base_path="/nonexistent", query_service=FailingQueryService()
        )
        bad_client = TestClient(create_app(cfg), raise_server_exceptions=False)
        resp = bad_client.get("/datasets")
        assert resp.status_code == 500
        body = resp.json()
        assert "error" in body
        assert body["code"] == 500


class TestOrderValidation:
    def test_invalid_order_returns_422(self, client, tmp_path):
        resp = client.get(f"/candles?path={tmp_path}&order=INVALID")
        assert resp.status_code == 422

    def test_valid_desc(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get(f"/candles?path={tmp_path}&order=DESC")
        assert resp.status_code == 200

    def test_valid_asc(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get(f"/candles?path={tmp_path}&order=ASC")
        assert resp.status_code == 200


class TestCORS:
    def test_cors_headers_present(self, client):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "*"
