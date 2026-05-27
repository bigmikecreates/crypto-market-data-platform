# Next Steps

## Done

- [x] Wire funding rate ingestion into CLI (FakeProvider + `FundingIngestionService` + `fetch-funding` command)
- [x] DuckDB query engine: `QueryService` ABC + `DuckDBQueryService` + CLI commands
- [x] FastAPI server (`create_app()`, CORS, error handling, Dockerfile)
- [x] REST endpoint definitions (health, datasets, candles, funding-rates, summary, query)

## Next

- [ ] **Bybit provider** (#2) — third live provider, tests provider ranking
- [ ] **Kraken provider** (#3) — edge-case: 720-candle limit, sparse markets
- [ ] **CI workflow** — provider smoke tests (`--live` flag, off by default)
- [ ] **Docs pass** — README updated with FundingRate, KuCoin, Network/CPU boundary, QueryService, server

## Tracking

- [#7](https://github.com/bigmikecreates/crypto-market-data-platform/issues/7) — Umbrella: query service layer
- [#6](https://github.com/bigmikecreates/crypto-market-data-platform/issues/6) — Engine: DuckDB impl + CLI (done)
- [#8](https://github.com/bigmikecreates/crypto-market-data-platform/issues/8) — Server: FastAPI hosting (done)
- [#9](https://github.com/bigmikecreates/crypto-market-data-platform/issues/9) — API: REST endpoints (done)
- [#2](https://github.com/bigmikecreates/crypto-market-data-platform/issues/2) — Bybit provider (pending)
- [#3](https://github.com/bigmikecreates/crypto-market-data-platform/issues/3) — Kraken provider (pending)
