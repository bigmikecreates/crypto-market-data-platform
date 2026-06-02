from fastapi.testclient import TestClient
from pytest import fixture

from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.server import create_app
from crmd_platform.server.config import ServerConfig
from crmd_platform.storage.parquet_writer import (
    write_candles,
    write_funding_rates,
)


@fixture
def client(tmp_path):
    cfg = ServerConfig(base_path=str(tmp_path))
    return TestClient(create_app(cfg))


@fixture
def authed_client(tmp_path):
    """Client for a server that requires X-API-Key: test-secret."""
    cfg = ServerConfig(base_path=str(tmp_path), api_key="test-secret")
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

    def test_health_exempt_from_auth(self, authed_client):
        """Load-balancer probes must reach /health without a key."""
        resp = authed_client.get("/health")
        assert resp.status_code == 200


class TestDatasets:
    def test_list_datasets_empty(self, client):
        resp = client.get("/datasets")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_list_datasets_with_data(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        _write_funding_fixtures(str(tmp_path))
        resp = client.get("/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert "ex_a/BTC/USDT/1h" in data["candle"]
        assert "ex_a/PI_XBTUSD/funding_rate" in data["funding_rate"]


class TestCandles:
    def test_get_candles_all(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get("/candles")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        assert rows[0]["symbol"] == "BTC/USDT"

    def test_get_candles_filter_symbol(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get("/candles?symbol=BTC/USDT")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2

    def test_get_candles_no_match(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get("/candles?symbol=DOGE/USDT")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_candles_limit_too_high(self, client):
        resp = client.get("/candles?limit=99999")
        assert resp.status_code == 422


class TestFundingRates:
    def test_get_funding_rates_all(self, client, tmp_path):
        _write_funding_fixtures(str(tmp_path))
        resp = client.get("/funding-rates")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["symbol"] == "PI_XBTUSD"

    def test_get_funding_rates_no_match(self, client, tmp_path):
        _write_funding_fixtures(str(tmp_path))
        resp = client.get("/funding-rates?symbol=DOGE")
        assert resp.status_code == 200
        assert resp.json() == []


class TestRawQuery:
    def test_raw_query(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.post(
            "/query",
            json={
                "sql": f"SELECT count(*) AS cnt FROM read_parquet('{tmp_path}/**/*.parquet')",
            },
        )
        assert resp.status_code == 200
        rows = resp.json()
        assert rows[0]["cnt"] == 2

    def test_raw_query_with_cte(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.post(
            "/query",
            json={"sql": "WITH q AS (SELECT 1 AS x) SELECT x FROM q"},
        )
        assert resp.status_code == 200

    def test_raw_query_blocks_copy(self, client):
        resp = client.post(
            "/query",
            json={"sql": "COPY (SELECT 1) TO '/tmp/out.csv'"},
        )
        assert resp.status_code == 400

    def test_raw_query_blocks_install(self, client):
        resp = client.post("/query", json={"sql": "INSTALL httpfs"})
        assert resp.status_code == 400

    def test_raw_query_blocks_create(self, client):
        resp = client.post("/query", json={"sql": "CREATE TABLE t AS SELECT 1"})
        assert resp.status_code == 400

    def test_raw_query_blocks_drop(self, client):
        resp = client.post("/query", json={"sql": "DROP TABLE t"})
        assert resp.status_code == 400

    def test_raw_query_invalid_body(self, client):
        resp = client.post("/query", json={})
        assert resp.status_code == 422


class TestSummary:
    def test_summary_empty(self, client):
        resp = client.get("/summary")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_summary_with_data(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        _write_funding_fixtures(str(tmp_path))
        resp = client.get("/summary")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        types = {r["type"] for r in rows}
        assert types == {"candle", "funding_rate"}
        for r in rows:
            if r["type"] == "candle":
                assert r["files"] == 2
                assert r["rows"] == 2
            else:
                assert r["files"] == 1
                assert r["rows"] == 1

    def test_summary_slash_symbol_parsed_correctly(self, client, tmp_path):
        """BTC/USDT must appear as symbol='BTC/USDT', not split across fields."""
        _write_candle_fixtures(str(tmp_path))
        resp = client.get("/summary")
        assert resp.status_code == 200
        candle_rows = [r for r in resp.json() if r["type"] == "candle"]
        assert len(candle_rows) == 1
        row = candle_rows[0]
        assert row["symbol"] == "BTC/USDT"
        assert row["timeframe"] == "1h"
        assert row["exchange"] == "ex_a"


class TestAuthentication:
    def test_dev_mode_allows_all_requests(self, client):
        """No key configured → open access."""
        resp = client.get("/datasets")
        assert resp.status_code == 200

    def test_correct_key_grants_access(self, authed_client, tmp_path):
        resp = authed_client.get("/datasets", headers={"X-API-Key": "test-secret"})
        assert resp.status_code == 200

    def test_missing_key_returns_401(self, authed_client):
        resp = authed_client.get("/datasets")
        assert resp.status_code == 401
        assert "API key" in resp.json()["detail"]

    def test_wrong_key_returns_401(self, authed_client):
        resp = authed_client.get("/datasets", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_auth_applied_to_all_data_endpoints(self, authed_client):
        for endpoint in ("/datasets", "/candles", "/funding-rates", "/summary"):
            resp = authed_client.get(endpoint)
            assert resp.status_code == 401, f"{endpoint} should require auth"

    def test_post_query_requires_auth(self, authed_client):
        resp = authed_client.post("/query", json={"sql": "SELECT 1"})
        assert resp.status_code == 401


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

        from crmd_platform.server.config import ServerConfig

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
    def test_invalid_order_returns_422(self, client):
        resp = client.get("/candles?order=INVALID")
        assert resp.status_code == 422

    def test_valid_desc(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get("/candles?order=DESC")
        assert resp.status_code == 200

    def test_valid_asc(self, client, tmp_path):
        _write_candle_fixtures(str(tmp_path))
        resp = client.get("/candles?order=ASC")
        assert resp.status_code == 200


class TestCORS:
    def test_allowed_origin_gets_cors_header(self, client):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert (
            resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        )

    def test_unlisted_origin_blocked(self, client):
        resp = client.options(
            "/datasets",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI CORS middleware omits the header when origin is not allowed
        assert "access-control-allow-origin" not in resp.headers
