# Next Steps

## Done

- [x] Bitfinex, KuCoin, Bybit, MEXC providers — all with fixture-based tests
- [x] Wire funding rate ingestion into CLI (FakeProvider + `FundingRateService` + `fetch-funding` command)
- [x] DuckDB query engine: `QueryService` ABC + `DuckDBQueryService` + CLI commands
- [x] FastAPI server (`create_app()`, CORS, error handling, Dockerfile)
- [x] REST endpoint definitions (health, datasets, candles, funding-rates, summary, query)
- [x] Docs pass — MkDocs Material site with 8 pages, GitHub Pages CI/CD via `mkdocs gh-deploy`

## Next (per #11 ranking)

1. [ ] **Bitstamp** — low-friction OHLC endpoint
2. [ ] **Gate.io** — broad altcoin coverage
3. [ ] **Coinbase Exchange** — clean API, gap-interval semantics
4. [ ] **OKX** — strategic Asia liquidity venue
5. [ ] **Gemini** — regulated US venue
6. [ ] **HTX / Huobi** — Asia liquidity, timestamp caveats
7. [ ] **Kraken** — low priority: since-based pagination, 720-candle limit

Also:
- [ ] **CI workflow** — provider smoke tests (`--live` flag, off by default)
- [ ] **Provider profile documentation** — per-provider docs write-up

## Deferred — ingestion network I/O optimisation

Benchmark profiles show real ingestion is overwhelmingly network-bound
(Net/CPU: Bitfinex 5.7×, KuCoin 30.1×).  Deferred until broad OHLCV
provider coverage is reached:

- [ ] Per-request latency tracking (page-level timing in fetch loop)
- [ ] Connection pooling (urllib.request → httpx keep-alive)
- [ ] Throughput reporting (candles/s during long backfills)
- [ ] Adaptive rate limiting (react to 429s, not hardcoded sleep)
- [ ] Concurrent page fetching (ThreadPoolExecutor for disjoint ranges)

## Tracking

- [#11](https://github.com/bigmikecreates/crypto-market-data-platform/issues/11) — Umbrella: data source provider implementation
- [#7](https://github.com/bigmikecreates/crypto-market-data-platform/issues/7) — Umbrella: query service layer (code done, issues stale)
- [#3](https://github.com/bigmikecreates/crypto-market-data-platform/issues/3) — Kraken provider (low priority, ranked 8th)
