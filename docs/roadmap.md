# Roadmap

## Short-term

- [ ] **Bybit provider** — third live provider, validates provider
      ranking and abstraction pattern at scale
- [ ] **Kraken provider** — edge-case provider with 720-candle limit
      and sparse market coverage; tests infrastructure at known
      constraints
- [ ] **CI workflow** — automated provider smoke tests (`--live` flag,
      off-by-default) to catch API contract drift
- [ ] **Documentation pass** — complete the MkDocs material site with
      case studies and API reference

## Medium-term

- [ ] **Replayable workloads** — capture provider responses as fixtures
      and replay them through the pipeline to isolate pipeline changes
      from API variability
- [ ] **Storage backends** — evaluate alternative storage layers
      (Postgres, InfluxDB, Parquet-over-S3) behind the `QueryService` ABC
- [ ] **Richer profiling** — per-provider breakdowns in the benchmark,
      histogram visualisation of latency distributions
- [ ] **Provider comparison** — systematic comparison of data quality,
      coverage, and API behaviour across all supported providers

## Long-term

- [ ] **Data quality scoring** — automated per-provider quality metrics
      (completeness, gap frequency, timestamp alignment)
- [ ] **Reproducible provider evaluation** — benchmark runs that compare
      providers head-to-head on identical time ranges
- [ ] **Strategy testing infrastructure** — event replay over stored
      market data for offline strategy evaluation
- [ ] **Market data observability** — ingestion health metrics, provider
      latency dashboards, data freshness alerts

Issue tracking is managed on GitHub.
