# HTTP API Reference

The REST server is started via `cmpd serve` or directly with:

```python
from crypto_market_data_platform.server import create_app
from crypto_market_data_platform.server.config import ServerConfig

config = ServerConfig(host="0.0.0.0", port=8000, base_path="data")
app = create_app(config)
```

OpenAPI/Swagger UI available at `http://localhost:8000/docs`.

## `GET /health`

Health check.

**Response:** `{"status": "ok"}`

## `GET /datasets`

List available datasets grouped by type.

| Query param | Default | Description |
|-------------|---------|-------------|
| `path` | `data` | Base data directory |

**Response:** `dict[str, list[str]]` — e.g. `{"candle": ["bitfinex/BTC/USDT/1h", ...], "funding_rate": [...]}`

## `GET /candles`

Query candle data.

| Query param | Default | Description |
|-------------|---------|-------------|
| `path` | `data` | Base data directory |
| `exchange` | — | Filter by exchange |
| `symbol` | — | Filter by symbol |
| `timeframe` | — | Filter by timeframe |
| `start` | — | Start timestamp (inclusive) |
| `end` | — | End timestamp (exclusive) |
| `limit` | `100` | Max rows (1–10 000) |
| `order` | `DESC` | Sort order (`DESC` or `ASC`) |

**Response:** `list[Candle]` (see [Data Model](/data-model/))

## `GET /funding-rates`

Query funding rate data.

| Query param | Default | Description |
|-------------|---------|-------------|
| `path` | `data` | Base data directory |
| `exchange` | — | Filter by exchange |
| `symbol` | — | Filter by symbol |
| `start` | — | Start timestamp (inclusive) |
| `end` | — | End timestamp (exclusive) |
| `limit` | `100` | Max rows (1–10 000) |
| `order` | `DESC` | Sort order (`DESC` or `ASC`) |

**Response:** `list[FundingRate]` (see [Data Model](/data-model/))

## `GET /summary`

Dataset summary with row counts per partition.

| Query param | Default | Description |
|-------------|---------|-------------|
| `path` | `data` | Base data directory |

**Response:** `list[dict]` with keys `type`, `exchange`, `symbol`, `timeframe`,
`files`, `rows`.

## `POST /query`

Run raw SQL via DuckDB `read_parquet`.

**Request body:**

```json
{
  "sql": "SELECT * FROM read_parquet('data/**/*.parquet') LIMIT 5",
  "path": "data"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sql` | `str` | required | SQL query |
| `path` | `str` | `data` | Base data directory |

**Response:** `list[dict]` — each row as a dict with `Decimal` → `str` and
`datetime` → ISO-8601 normalisation.
