# Manual Review Guide — SDK + CLI Refactor

This guide helps a product engineer verify that the SDK and CLI changes work as intended. You don't need to know the internals of DuckDB, FastAPI, or Parquet — just run the commands and check the outputs.

---

## What this change does (in plain English)

Before: If you wanted to use the platform from Python code, you had to import internal modules and wire them up yourself. The CLI was the only polished user interface.

After: There's a single `Client` class that gives you access to everything — query data, fetch new data, list datasets — whether you're running locally on your machine or pointing at a remote server. The CLI now uses this same class internally, so it gets the new capabilities too (like a `--remote` flag to talk to a deployed server).

---

## Quick reference table

| What to test | How to test it | What should happen |
|---|---|---|
| SDK imports cleanly | `from crmd_platform import Client` | No errors |
| Local SDK works | `Client.local()` | Returns a client object |
| Remote SDK works | `Client.remote("http://localhost:8050")` | Returns a client object |
| CLI still works | `crmd datasets` | Lists your parquet datasets (same as before) |
| CLI remote works | `crmd datasets --remote http://localhost:8050` | Same output, but fetched over HTTP |
| CLI fetch works | `crmd fetch --mdt ohlcv --symbol BTC/USDT --timeframe 1h --provider fake --start 2026-01-01` | Writes fake candle data |
| CLI help shows new flag | `crmd fetch --help` | Shows `--remote` option |
| CLI starts fast | `python -c "import crmd_platform.cli.main"` | Doesn't load DuckDB or FastAPI at import time |

---

## 1. SDK: Using the platform from Python code

The `Client` class is the new way to interact with the platform from Python scripts, notebooks, or any code.

### 1a. Basic sanity check

```python
from crmd_platform import Client
client = Client.local("data")
print("Client created — looking for datasets...")

ds = client.list_datasets()
print(ds)
```

**What to look for:** A dictionary listing your available candle and funding-rate datasets. You should see entries like `{'candle': ['bitfinex/BTC/USD/1h', ...], 'funding_rate': [...]}`. Dataset keys should not include `fake/` datasets — those are filtered out automatically.

### 1b. Query the last 5 candles

```python
candles = client.query_candles(limit=5)
print(f"Got {len(candles)} candles")
for c in candles:
    print(f"{c.exchange} | {c.symbol} | {c.timestamp} | O:{c.open} C:{c.close}")
```

**What to look for:** 5 rows of candle data with exchange, symbol, timestamp, open/close prices. Same data the CLI shows.

### 1c. Filter by exchange and symbol

```python
candles = client.query_candles(exchange="bitstamp", symbol="BTC/USD", limit=3)
print(f"Got {len(candles)} candles")
assert all(c.exchange == "bitstamp" for c in candles)
```

**What to look for:** All returned rows should be from bitstamp BTC/USD.

### 1d. Run a SQL query

```python
rows = client.query_sql("SELECT COUNT(*) AS cnt FROM read_parquet('data/**/*.parquet') LIMIT 3")
print(rows)
```

**What to look for:** A small table with the count of total rows across all parquet files.

### 1e. Get dataset summaries

```python
summary = client.get_summary()
for row in summary:
    print(f"{row['type']:12s} {row['exchange']:10s} {row['symbol']:12s} files={row['files']} rows={row['rows']}")
```

**What to look for:** A table showing each dataset, how many parquet files it spans, and total row count.

### 1f. Fetch new data

```python
result = client.fetch_candles(
    provider="fake",
    symbol="BTC/USDT",
    timeframe="1h",
    start="2026-01-01",
    end="2026-01-02",
)
print(f"Wrote {result.count} candles for {result.symbol}")
```

**What to look for:** A message saying how many candles were written. This uses the fake provider so it works without exchange API credentials.

### 1g. What happens if you make a mistake?

Good error messages are a feature. Try these:

```python
# Unknown provider
client.fetch_candles(provider="nope", symbol="BTC/USDT", timeframe="1h", start="2026-01-01")
# → "Unknown provider 'nope'. Available: fake, bitfinex, bitstamp, bybit, kucoin, mexc"

# Provider that doesn't support funding rates
client.fetch_funding_rates(provider="bitfinex", symbol="tBTCUSD", start="2026-01-01")
# → "Provider 'bitfinex' does not support funding rates"
```

**What to look for:** Clear English error messages that tell you *what* went wrong and *how to fix it*. No stack traces.

---

## 2. SDK: Remote mode (requires a running server)

This tests the same SDK but talking to a server over HTTP. You need the server running.

**Terminal 1 — start the server:**
```bash
crmd serve --api-key test-key-123
```

**Terminal 2 — test the remote client:**
```python
from crmd_platform import Client
client = Client.remote("http://localhost:8050", api_key="test-key-123")

# Same methods as local
ds = client.list_datasets()
candles = client.query_candles(limit=3)
summary = client.get_summary()
result = client.fetch_candles(provider="fake", symbol="BTC/USDT", timeframe="1h", start="2026-01-01")
```

**What to look for:** Everything returns the same shapes as the local client. The candle objects should still have `.exchange`, `.symbol`, `.timestamp`, etc.

### What happens without auth?

```python
client2 = Client.remote("http://localhost:8050")  # no API key
client2.list_datasets()
```

- If the server was started with `--api-key` → should fail with a permission error
- If the server was started without `--api-key` (dev mode) → should work fine

### What happens with a wrong API key?

```python
client3 = Client.remote("http://localhost:8050", api_key="wrong-key")
client3.list_datasets()
```

**What to look for:** A clear `PermissionError` message — not a raw HTTP 401.

---

## 3. CLI: Same commands, more flexibility

The CLI commands you already know (`crmd datasets`, `crmd query`, `crmd fetch`) work exactly as before, but now they have an optional `--remote` flag.

### 3a. CLI still works as before

```bash
# These should all produce the same output as they always did
crmd datasets
crmd query ohlcv --limit 5
crmd query ohlcv --exchange bitstamp --symbol BTC/USD --limit 3
crmd query sql "SELECT COUNT(*) AS cnt FROM read_parquet('data/**/*.parquet')"
crmd fetch --mdt ohlcv --symbol BTC/USDT --timeframe 1h --provider fake --start 2026-01-01 --end 2026-01-02
```

**What to look for:** Same formatting, same columns, same behaviour as before. Nothing broke.

### 3b. CLI remote mode (same commands, remote server)

```bash
# With server running on port 8050:
crmd datasets --remote http://localhost:8050
crmd query ohlcv --remote http://localhost:8050 --limit 5
crmd fetch --mdt ohlcv --symbol BTC/USDT --timeframe 1h --provider fake --start 2026-01-01 --remote http://localhost:8050
```

**What to look for:** Same output format as local, but data comes from the server. You can tell by running the server with different data and seeing it reflected.

### 3c. Environment variable shortcut

Instead of typing `--remote` every time, you can set an env var:

```bash
export CRMD_API_URL=http://localhost:8050
crmd query ohlcv --limit 3   # auto-detects remote mode
unset CRMD_API_URL
```

**What to look for:** Works the same as `--remote`. If both env var and `--remote` are set, `--remote` wins.

### 3d. CLI — the --remote flag appears in help

```bash
crmd fetch --help           # should mention --remote
crmd datasets --help        # should mention --remote
crmd query ohlcv --help     # should mention --remote
crmd serve --help           # should NOT mention --remote (it IS the server)
crmd inspect --help         # should NOT mention --remote (filesystem tool)
```

---

## 4. Installing only what you need

The package now lets you install only the parts you need:

### 4a. Remote-only (lightweight, no DuckDB)

```bash
pip install /path/to/crmd-platform[remote]

# Remote client works
python -c "from crmd_platform import Client; c = Client.remote('http://x'); print('OK')"

# Local client tells you what's missing
python -c "from crmd_platform import Client; c = Client.local()"
# → ImportError: Local mode requires duckdb and pyarrow.
#    Install: pip install crmd-platform[local]
```

**What to look for:** Clear, helpful error. Not a raw `ModuleNotFoundError`.

### 4b. Full local + CLI

```bash
pip install /path/to/crmd-platform[cli]
crmd datasets   # works, includes DuckDB
```

### 4c. Everything

```bash
pip install /path/to/crmd-platform[all]
# Client.local() + Client.remote() + server + CLI — everything works
```

---

## 5. Things that should definitely fail (gracefully)

| Situation | What to try | What should happen |
|---|---|---|
| No server running | `crmd datasets --remote http://localhost:9999` | Connection error, not a hang or crash |
| Bad API key | `crmd query ohlcv --remote http://localhost:8050` (server has auth) | Error about authentication |
| Wrong provider type | See section 1g | Clear error about interface mismatch |
| Non-SELECT SQL locally | `crmd query sql "DROP TABLE t"` | "Only SELECT/WITH permitted" |
| Server unavailable | `Client.remote("http://localhost:9999").list_datasets()` | Connection error |
| Missing optional dep | `pip install crmd-platform[remote]` then `Client.local()` | "Install: pip install crmd-platform[local]" |

---

## 6. Run the test suite

This is the definitive check — 444 tests that validate everything end-to-end:

```bash
pip install -e ".[all,test]"
pytest -x --tb=short 2>&1 | tail -5
```

**Expected:** "444 passed, 13 skipped". Takes about 3 minutes.

If any tests fail, the output will say exactly which test failed and why — flag that for the engineering team.

---

## Checklist summary

- [ ] `from crmd_platform import Client` imports without error
- [ ] `Client.local()` queries return candle data
- [ ] `Client.remote(url)` queries return candle data (when server is running)
- [ ] `crmd datasets` same as before
- [ ] `crmd datasets --remote http://localhost:8050` works
- [ ] `crmd fetch --help` shows `--remote` flag
- [ ] Error messages are helpful (wrong provider, wrong API key, missing deps)
- [ ] `pip install crmd-platform[remote]` + remote client works, local client gives helpful error
- [ ] All 444 tests pass

When you're satisfied, delete this file and `DOCUMENTATION_REVIEW.md` and report back.
