# Smoke Testing

The smoke testing system validates that each provider's live API endpoint is
reachable and returns parseable OHLCV data. It makes real HTTP requests to the
exchange — no mocking, no fixtures, no API keys required for public endpoints.

Unlike the unit tests (`pytest tests/`), smoke tests depend on network access
and the live exchange API. They are designed to catch API contract drift,
deprecation, and downtime that unit tests cannot detect.

---

## Quick start

```bash
pip install -e .[dev]
python -m scripts.smoke --provider bitfinex
```

Example output:

```
Provider smoke test: bitfinex
  API version: old=v2, detected=v2 (unchanged)
  Outcome: PASS
  (3/3 passed, 0/3 failed)

  1: BTC/USD - HTTP 200 - Parse OK
  2: ETH/USD - HTTP 200 - Parse OK
  3: BTC/USDT - HTTP 200 - Parse OK
```

---

## CLI

| Flag | Required | Choices | Default | Description |
|------|----------|---------|---------|-------------|
| `--provider` | yes | `bitfinex`, `bitstamp`, `bybit`, `kucoin`, `mexc`, `coinbase`, `okx`, `gemini`, `htx`, `kraken` | — | Provider to test |
| `--format` | no | `text`, `markdown` | `text` | Output format |

**Pass/fail:** 3 attempts per run; passes if fewer than 2 fail. Exit code 0 on
pass, 1 on failure.

**Markdown output** is designed for CI issue filing:

```bash
python -m scripts.smoke --provider kraken --format markdown
```

---

## How it works

1. **`scripts/smoke/config.py`** — per-provider symbol lists, API version
   strings, and endpoint URL builders. Each builder receives a canonical
   symbol (e.g. `BTC/USD`), a start time, and an end time, and returns a
   fully-formed REST URL.

2. **`scripts/smoke/runner.py`** — makes 3 HTTP requests via `urllib` (no
   exchange SDK dependencies), cycling through the provider's configured
   symbols. Tracks HTTP status, redirects (for API version drift detection),
   and raw response body.

3. **`scripts/smoke/parsers.py`** — forwards the raw JSON response to the
   provider's own `_parse_row()` function. A parse error (exception, missing
   field, wrong type) counts as a failed attempt.

### API version drift detection

When the provider redirects to a different URL path, the `runner` compares the
original and final URL for version changes (e.g. `v2` → `v3`). This is logged
in every report and flagged in CI issues.

---

## CI integration

The workflow `.github/workflows/provider-smoke.yml`:

- **Schedule:** Every Monday at 06:00 UTC (`0 6 * * 1`)
- **Manual trigger:** `workflow_dispatch` via GitHub UI or API
- **Matrix:** All 10 providers run in parallel with `fail-fast: false`
- **On failure:** Creates or updates a GitHub issue titled `"Provider smoke
  failure: <provider>"` with the `provider-smoke` label and a markdown report.

---

## Adding a new provider

1. Add symbols to `SYMBOLS` in `scripts/smoke/config.py`
2. Add API version to `API_VERSIONS`
3. Write an endpoint builder function and add it to `ENDPOINTS`
4. Add a `parse_via_provider` branch in `scripts/smoke/parsers.py` that
   calls the new provider's `_parse_row()`
5. Add the provider to `choices` in `parse_args()` (the `ArgumentParser`)
6. Add the provider to the CI matrix in
   `.github/workflows/provider-smoke.yml`

---

## Notes

- No API keys are needed for any of the 10 configured providers (public
  endpoints only).
- The smoke system imports and depends on `crmd_platform` — run `pip install
  -e .` first.
- Raw response bodies are truncated at 2048 bytes in reports
  (`OUTPUT_TRUNCATE` in `config.py`).
- There are no unit tests for the smoke system itself — it tests live
  endpoints by design.

---

## Reference

- `scripts/smoke/config.py` — symbols, API versions, endpoint builders
- `scripts/smoke/parsers.py` — response parsing via provider `_parse_row()`
- `scripts/smoke/runner.py` — HTTP fetching, result formatting, CLI entry
  point
- `.github/workflows/provider-smoke.yml` — CI workflow definition
