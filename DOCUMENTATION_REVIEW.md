# Documentation Review — Design Philosophy

This document explains the thinking behind the SDK and CLI changes, written for a product engineer who wants to understand *why* we built it this way (not just *what* changed).

---

## 1. One `Client` class for everything

**The idea:**

There's one class — `Client` — that does everything: query data, fetch new data, list datasets. You create it with either `Client.local()` for local files or `Client.remote(url)` for a server, then call the same methods (`query_candles()`, `fetch_candles()`, etc.).

**Why it matters for users:**

- A user who starts with `Client.local()` on their laptop can switch to `Client.remote("https://api.prod.example.com")` when they deploy to production — without changing any of the query/fetch code. The data source changes, the code doesn't.
- New users learn one class, not three (`DuckDBQueryService` + `OHLCVService` + some HTTP library). Lower learning curve.

**What we avoided:**

We considered exposing the internal services directly and letting users wire them up. That would make users learn the internal architecture (query vs fetch split, parameter wiring) before they can do anything useful. Bad first experience.

---

## 2. You explicitly choose local or remote

**The idea:**

You write `Client.local()` or `Client.remote(some_url)`. There's no auto-detection that guesses which one you want.

**Why it matters for users:**

- Choosing local vs remote is a deliberate decision — running on your machine vs. talking to a deployed server. You shouldn't be surprised by which one you're using.
- If auto-detection tried to guess and guessed wrong (e.g., server is down → silently falls back to local), you'd get confused about why your data looks different.
- `Client.remote("https://api.prod.example.com")` leaves no doubt about what's happening. Code review, debugging, documentation — it's clear.

**The one exception — CLI convenience:**

The CLI has a `--remote` flag and reads `CRMD_API_URL` from the environment. That's because the CLI is a tool you run repeatedly — you don't want to type `--remote` on every command. But in Python code (scripts, notebooks), we keep it explicit.

---

## 3. The CLI starts fast and doesn't crash on a partial install

**The idea:**

Running `crmd --help` should show help instantly, even if you only installed the remote package (no DuckDB).

**Why it matters for users:**

- If you do `pip install crmd-platform[remote]` and type `crmd --help`, you expect help text, not a crash. That's what happens now.
- If you type `crmd fetch --remote ...`, the CLI should start immediately — it shouldn't first load DuckDB, PyArrow, and FastAPI when you're not using them.

**How it works:**

The CLI only imports what's absolutely necessary at startup (`typer` and the `Client` class). Everything else — DuckDB, FastAPI, uvicorn — is loaded only when you actually run a command that needs it.

---

## 4. One package, optional extras

**The idea:**

There's one package (`crmd-platform`), not separate packages for local vs remote. You choose what to install with extras:

- `pip install crmd-platform` → local mode (DuckDB, PyArrow)
- `pip install crmd-platform[remote]` → HTTP client only (httpx)
- `pip install crmd-platform[server]` → full server
- `pip install crmd-platform[cli]` → CLI + local

**Why it matters for users:**

- A remote-only user never installs DuckDB. Lightweight install, no wasted disk space.
- A local user doesn't install FastAPI/uvicorn/httpx.
- No coordination headaches — one version, one changelog, one place to file bugs.

**What happens if you try local mode without DuckDB?**

You get a clear message: "Install: pip install crmd-platform[local]", not a raw Python error.

---

## 5. The SDK validates providers early

**The idea:**

If you try to fetch funding rates from a provider that only supports OHLCV candles, the SDK tells you immediately with a clear message: "Provider 'bitfinex' does not support funding rates."

**Why it matters for users:**

Without this, you'd get a confusing error much later (like "AttributeError: 'BitfinexProvider' object has no attribute 'fetch_funding_rates'") with no explanation of why or what to do. We catch it early and explain the fix.

---

## 6. The CLI does loops, the SDK does one thing

**The idea:**

The SDK's `fetch_candles()` fetches one symbol, one time range, no loops. If you want to fetch continuously until caught up (`--since-last`), that logic lives in the CLI.

**Why it matters for users:**

- A script that just wants today's candles shouldn't need to understand `--since-last` loop semantics. It calls `fetch_candles(start=today, end=today)` and gets data back. Simple.
- Different consumers want different loop behaviour: a cron job might run once a day, a Jupyter notebook might fetch interactively, a production pipeline might stream continuously. The SDK shouldn't pick one. The CLI can offer a convenient loop for terminal users.
- Same logic applies to multi-symbol fetching. The SDK fetches one symbol; the CLI fans out to many with `ThreadPoolExecutor`.

---

## 7. Remote mode returns the same objects as local mode

**The idea:**

`Client.local().query_candles(...)` and `Client.remote(url).query_candles(...)` take the same parameters and return the same Python objects (`Candle`, `FundingRate`).

**Why it matters for users:**

- You write your analysis code once. Run it locally for development, point at a server for production. No adapter layer, no conversion code.
- The remote client deserialises the server's JSON responses back into the exact same dataclass types.

---

## 8. Existing CLI users notice nothing changed

**The idea:**

Every existing command (`crmd datasets`, `crmd query ohlcv`, `crmd fetch`) produces exactly the same output as before the refactor.

**Why it matters for users:**

- No retraining, no broken scripts, no "why does this look different today?" moments.
- The refactor's goal is to add new capabilities (SDK, remote mode), not to change existing behaviour.

---

## How it all fits together

```
User's Python script or CLI
         │
         ▼
  ┌─────────────┐    ┌──────────────┐
  │ Client.local │    │Client.remote │
  │ (DuckDB)     │    │ (httpx       │
  │              │    │  -> server)  │
  └──────┬──────┘    └──────┬───────┘
         │                  │
         ▼                  │
  ┌──────────────┐          │
  │ Internal     │          │
  │ services     │◄─────────┘
  │ (unchanged)  │   HTTP call to
  │              │   existing API
  └──────────────┘
```

- The SDK is a new thin layer on top. Everything below it (the internal services, the providers, the storage) is unchanged.
- `Client.local()` delegates to the same `DuckDBQueryService` and `OHLCVService` the CLI used directly before.
- `Client.remote()` is a pure HTTP wrapper over the existing FastAPI endpoints — the server didn't change at all.
