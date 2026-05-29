# HTTP API Reference

The REST server is started via `cmpd serve` or programmatically via [`create_app`](python-api.md#crypto_market_data_platformserver).

OpenAPI/Swagger UI is available at `http://localhost:8000/docs` when the server is running.

---

## `GET /health`

Health check endpoint.

### Usage

```bash
curl http://localhost:8000/health
```

### Examples

Success:

```bash
$ curl http://localhost:8000/health
{"status": "ok"}
```

---

## `GET /datasets`

List available datasets grouped by type.

### Usage

```bash
curl "http://localhost:8000/datasets?path=data"
```

### Options

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `path` | `str` | `"data"` | Base data directory |

### Examples

Success:

```bash
$ curl "http://localhost:8000/datasets"
{"candle": ["bitfinex/BTC/USD/1h"], "funding_rate": []}
```

Error — nonexistent path returns empty groups:

```bash
$ curl "http://localhost:8000/datasets?path=/nonexistent"
{"candle": [], "funding_rate": []}
```

---

## `GET /candles`

Query candle data.

### Usage

```bash
curl "http://localhost:8000/candles?exchange=bitfinex&symbol=BTC/USD&limit=3"
```

### Options

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `path` | `str` | `"data"` | Base data directory |
| `exchange` | `str` | — | Filter by exchange |
| `symbol` | `str` | — | Filter by symbol |
| `timeframe` | `str` | — | Filter by timeframe |
| `start` | ISO-8601 | — | Start timestamp (inclusive) |
| `end` | ISO-8601 | — | End timestamp (exclusive) |
| `limit` | `int` | `100` | Max rows (1–10 000) |
| `order` | `str` | `"DESC"` | Sort order: `DESC` or `ASC` |

### Examples

Success:

```bash
$ curl "http://localhost:8000/candles?exchange=bitfinex&limit=2"
[
  {"exchange":"bitfinex","symbol":"BTC/USD","timeframe":"1h","timestamp":"2024-01-01T01:00:00","open":"42509","high":"42811","low":"42482","close":"42678","volume":"21.5892983","source":"bitfinex"},
  {"exchange":"bitfinex","symbol":"BTC/USD","timeframe":"1h","timestamp":"2024-01-01T00:00:00","open":"42331","high":"42591","low":"42331","close":"42522","volume":"9.03426154","source":"bitfinex"}
]
```

Error — no matching data:

```bash
$ curl "http://localhost:8000/candles?exchange=nonexistent"
[]
```

---

## `GET /funding-rates`

Query funding rate data.

### Usage

```bash
curl "http://localhost:8000/funding-rates?exchange=fake&limit=3"
```

### Options

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `path` | `str` | `"data"` | Base data directory |
| `exchange` | `str` | — | Filter by exchange |
| `symbol` | `str` | — | Filter by symbol |
| `start` | ISO-8601 | — | Start timestamp (inclusive) |
| `end` | ISO-8601 | — | End timestamp (exclusive) |
| `limit` | `int` | `100` | Max rows (1–10 000) |
| `order` | `str` | `"DESC"` | Sort order: `DESC` or `ASC` |

### Examples

Success:

```bash
$ curl "http://localhost:8000/funding-rates?exchange=fake&limit=2"
[
  {"exchange":"fake","symbol":"BTC/USDT","timestamp":"2026-05-27T00:00:00","rate":"0.0001","predicted_rate":"0.0002","next_funding_time":"2026-01-01T16:00:00","source":"fake"}
]
```

Error — no matching data:

```bash
$ curl "http://localhost:8000/funding-rates?exchange=nonexistent"
[]
```

---

## `GET /summary`

Dataset summary with row counts per partition.

### Usage

```bash
curl "http://localhost:8000/summary?path=data"
```

### Options

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `path` | `str` | `"data"` | Base data directory |

### Examples

Success:

```bash
$ curl "http://localhost:8000/summary"
[
  {"type":"candle","exchange":"bitfinex","symbol":"BTC/USD","timeframe":"1h","files":4,"rows":144}
]
```

Error — empty data directory:

```bash
$ curl "http://localhost:8000/summary?path=/nonexistent"
[]
```

---

## `POST /query`

Run raw SQL via DuckDB `read_parquet`.

### Usage

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM read_parquet('"'"'data/**/*.parquet'"'"') LIMIT 2", "path": "data"}'
```

### Request body

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sql` | `str` | required | SQL query using `read_parquet('data/**/*.parquet')` |
| `path` | `str` | `"data"` | Base data directory |

### Examples

Success:

```bash
$ curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT COUNT(*) AS cnt FROM read_parquet('"'"'data/**/*.parquet'"'"')"}'
[{"cnt": 144}]
```

Error — bad SQL:

```bash
$ curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM nonexistent"}'
{"error": "Catalog Error: Table with name nonexistent does not exist!", "code": 500}
```
