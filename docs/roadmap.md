# Roadmap

## Completed

- [x] **Bybit provider** — live provider integrated; validates provider abstraction at scale
- [x] **MEXC provider** — fifth live exchange, broadens data-source coverage
- [x] **CI smoke tests** — weekly automated provider smoke tests with automatic GitHub Issue
      creation and deduplication on failure
- [x] **Documentation site** — MkDocs Material user guide + Docsify API reference

## Short-term

- [ ] **Kraken provider** — edge-case provider with 720-candle limit and sparse market
      coverage; tests infrastructure at known constraints
- [ ] **Replayable provider fixtures** — capture provider responses as test fixtures and
      replay through the pipeline to isolate pipeline changes from live API variability
- [ ] **Coverage gate** — enforce a minimum coverage threshold in CI once property-based
      test coverage stabilises

## Medium-term

- [ ] **Storage backends** — evaluate alternative storage layers (Postgres, InfluxDB,
      Parquet-over-S3) behind the `QueryService` ABC
- [ ] **Richer profiling** — per-provider breakdowns in the benchmark, histogram
      visualisation of latency distributions
- [ ] **Provider comparison** — systematic comparison of data quality, coverage, and API
      behaviour across all supported providers
- [ ] **Funding rate providers** — implement `FundingRateProvider` for at least one live
      exchange (Bybit or MEXC both expose funding rate APIs)

## Long-term

- [ ] **Data quality scoring** — automated per-provider quality metrics (completeness,
      gap frequency, timestamp alignment)
- [ ] **Reproducible provider evaluation** — benchmark runs that compare providers
      head-to-head on identical time ranges
- [ ] **Market data observability** — ingestion health metrics, provider latency
      dashboards, data freshness alerts

Issue tracking is managed on GitHub.
