# HTTP API Reference

The REST server is started via `crmd serve` or programmatically via [`create_app`](python-api.md#crmd_platformserver).

OpenAPI/Swagger UI is available at `http://localhost:8050/docs` when the server is running.

---

## Authentication

When the server is started with `--api-key` (or `CRMD_API_KEY` env var), all data endpoints require an `X-API-Key` header. `/health` is always exempt.

```bash
# Start with a key
export CRMD_API_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
crmd serve --path data

# Pass the key in every request
curl -H "X-API-Key: $CRMD_API_KEY" http://localhost:8050/datasets
```

Missing or wrong key returns `401`:

```json
{"detail": "Invalid or missing API key."}
```

When no key is configured the server runs in **open dev mode** and logs a warning on startup. Do not expose an unauthenticated server on a public interface.

---

## Data path

All data endpoints query the storage root configured at startup (`crmd serve --path`). The path is fixed — callers cannot override it per request. To query a different storage root, start a separate server instance.

---

## `GET /health`

Health check endpoint. Always exempt from authentication.

### Usage

```bash
curl http://localhost:8050/health
```

### Examples

```bash
$ curl http://localhost:8050/health
{"status": "ok"}
```

---

## `GET /datasets`

List available datasets grouped by type.

### Usage

```bash
curl -H "X-API-Key: $KEY" "http://localhost:8050/datasets"
```

### Options

No query parameters. The data directory is fixed by the server's `--path` setting.

### Examples

```bash
$ curl -H "X-API-Key: $KEY" "http://localhost:8050/datasets"
{"candle": ["bitfinex/BTC/USD/1h"], "funding_rate": []}
```

Empty directory returns empty groups:

```bash
$ curl -H "X-API-Key: $KEY" "http://localhost:8050/datasets"
{}
```

---

## `GET /candles`

Query candle data.

### Usage

```bash
curl -H "X-API-Key: $KEY" "http://localhost:8050/candles?exchange=bitfinex&symbol=BTC/USD&limit=3"
```

### Options

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `exchange` | `str` | — | Filter by exchange |
| `symbol` | `str` | — | Filter by symbol (exact match) |
| `timeframe` | `str` | — | Filter by timeframe |
| `start` | ISO-8601 | — | Start timestamp (inclusive) |
| `end` | ISO-8601 | — | End timestamp (exclusive) |
| `limit` | `int` | `100` | Max rows (1–10 000) |
| `order` | `str` | `"DESC"` | Sort order: `DESC` or `ASC` |

### Examples

```bash
$ curl -H "X-API-Key: $KEY" "http://localhost:8050/candles?exchange=bitfinex&limit=2"
[
  {"exchange":"bitfinex","symbol":"BTC/USD","timeframe":"1h","timestamp":"2024-01-01T01:00:00","open":"42509","high":"42811","low":"42482","close":"42678","volume":"21.5892983","source":"bitfinex"},
  {"exchange":"bitfinex","symbol":"BTC/USD","timeframe":"1h","timestamp":"2024-01-01T00:00:00","open":"42331","high":"42591","low":"42331","close":"42522","volume":"9.03426154","source":"bitfinex"}
]
```

No matching data:

```bash
$ curl -H "X-API-Key: $KEY" "http://localhost:8050/candles?exchange=nonexistent"
[]
```

---

## `GET /funding-rates`

Query funding rate data.

### Usage

```bash
curl -H "X-API-Key: $KEY" "http://localhost:8050/funding-rates?exchange=fake&limit=3"
```

### Options

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `exchange` | `str` | — | Filter by exchange |
| `symbol` | `str` | — | Filter by symbol (exact match) |
| `start` | ISO-8601 | — | Start timestamp (inclusive) |
| `end` | ISO-8601 | — | End timestamp (exclusive) |
| `limit` | `int` | `100` | Max rows (1–10 000) |
| `order` | `str` | `"DESC"` | Sort order: `DESC` or `ASC` |

### Examples

```bash
$ curl -H "X-API-Key: $KEY" "http://localhost:8050/funding-rates?exchange=fake&limit=2"
[
  {"exchange":"fake","symbol":"BTC/USDT","timestamp":"2026-05-27T00:00:00","rate":"0.0001","predicted_rate":"0.0002","next_funding_time":"2026-01-01T16:00:00","source":"fake"}
]
```

---

## `GET /summary`

Dataset summary with row and file counts.

### Usage

```bash
curl -H "X-API-Key: $KEY" "http://localhost:8050/summary"
```

### Options

No query parameters.

### Examples

```bash
$ curl -H "X-API-Key: $KEY" "http://localhost:8050/summary"
[
  {"type":"candle","exchange":"bitfinex","symbol":"BTC/USD","timeframe":"1h","files":4,"rows":144}
]
```

---

## `POST /query`

Run raw SQL via DuckDB `read_parquet`. Only `SELECT` and `WITH … SELECT` statements are accepted. Semicolons outside string literals are rejected to prevent statement stacking.

### Usage

```bash
curl -X POST http://localhost:8050/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"sql": "SELECT COUNT(*) AS cnt FROM read_parquet('"'"'data/**/*.parquet'"'"')"}'
```

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sql` | `str` | yes | `SELECT` or `WITH … SELECT` statement. Embed paths directly in `read_parquet(...)`. |

### Examples

```bash
$ curl -s -X POST http://localhost:8050/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"sql": "SELECT COUNT(*) AS cnt FROM read_parquet('"'"'data/**/*.parquet'"'"')"}'
[{"cnt": 144}]
```

Blocked statement:

```bash
$ curl -X POST http://localhost:8050/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"sql": "COPY (SELECT 1) TO '"'"'/tmp/out.csv'"'"'"}'
{"detail": "Only SELECT (or WITH … SELECT) statements are permitted."}
```

---

← [API Reference Overview](overview.md)
