# Provider Selection Strategy — Validation-Layer Hardening

## Problem

The initial assumption was to start with shallow/limited providers
(e.g., Kraken) because their constraints expose edge cases early.
This proved backwards. A constrained provider tests the validation
layer less, not more — its limits are hit immediately, exercising
only the beginning of the pagination loop, a single partition, and
none of the ordering or partitioning correctness logic.

## Decision

Reverse the priority. Start with the provider that:

- returns the most candles per call (stresses batch size, partitioning
  breadth, and append correctness)
- has the deepest history (stresses backfill pagination)
- has the lowest integration friction (no sign-up, no auth, clean docs)

Rank providers by how much validation-layer stress they generate:

1. **OHLC granularity** — does the provider support multiple timeframes
   that produce different batch sizes and partition counts?
2. **Historical depth** — how far back does the data go? More total
   candles = more pages = more pagination-edge-case exposure.
3. **Pagination/backfill pressure** — does the provider force the
   caller to loop? Large per-call limits reduce page count but shift
   stress to batch size, partitioning, and write throughput.
4. **Timestamp ordering behaviour** — are candles always ascending?
   Can two requests overlap? Does the provider return future candles?
5. **Partitioning pressure** — do the retrieved candles span multiple
   dates? More date boundaries = more partition files = more
   correctness checks.
6. **Current/incomplete candle semantics** — does the provider include
   a partial current candle? If so, the pipeline must strip or label it.
7. **Sparse/no-tick interval behaviour** — does the provider omit
   intervals with no trades? This affects completeness validation and
   row-count expectations.
8. **Low integration friction** — no API key, no sign-up, REST-only,
   clean documentation.

Use shallow/constrained providers (e.g., Kraken) **later** as targeted
edge-case tests against a validation layer already proven at scale.

## Recommended Top 3 for MVP Validation Development

### 1. Bitfinex — Start Here

**Access:**
- Cost: Free
- Sign-up required: No
- API key required for public candles: No

**Why ranked first:**
- Public `candles` endpoint supports `limit` up to **10,000 records**
  per call — the largest single-page batch of any major exchange.
- Supports `start`/`end` timestamp windows — no offset-based
  pagination, reducing implementation roughness.
- Deep history across all major pairs.
- Clean JSON response format with few surprises.
- High per-call depth means fewer pages to cover a date range,
  which makes debugging the provider adapter simpler during initial
  integration.

**Validation value:**
- **Large batch size:** 10,000 candles per call stresses
  `Candle` list construction, `validate_candle_batch()`, and
  `write_candles()` in a single page — no pagination header needed.
- **Date partition stress:** 10,000 candles at 1m granularity span
  ~7 days — enough to exercise multi-partition writes and row-count
  verification without looping.
- **Timestamp ordering:** Candles arrive ascending; the pipeline
  confirms this invariant and surfaces any provider deviation.
- **Append/write correctness:** Multiple fetches for the same range
  exercise the existing-file append path in `write_candles()`.
- **Decimal conversion at scale:** 10,000 numeric string →
  `decimal128(38,10)` casts per page exercise the C++ `.cast()` path
  with real data.
- **Provider adapter parsing:** Real JSON response with real Kraken
  naming conventions exercises the `MarketDataProvider` interface.

**Expected MVP use:**
- Implement as the first real provider.
- Fetch enough candles to span multiple date partitions.
- Validate row counts per partition.
- Validate no writer-induced duplicates.
- Benchmark the full `Provider → Candle[] → validate → Parquet` path.
- No pagination is needed for 5,000–7,000 candles per call, keeping
  initial integration simple.

**Caveats:**
- Need to handle Bitfinex symbol naming conventions (e.g., `tBTCUSD`).
- Need to confirm candle timestamp semantics during implementation
  (open time vs close time).

---

### 2. KuCoin — Second Provider

**Access:**
- Cost: Free
- Sign-up required: No
- API key required for public klines: No

**Why ranked second:**
- High enough per-query depth (~1,500 candles) to test pagination.
- Public `klines` endpoint with time-window retrieval model.
- Known behaviour: intervals with no trades may be omitted —
  this is the first test of our completeness assumptions.

**Validation value:**
- **Pagination/windowing behaviour:** The pipeline must loop to
  cover a full date range — exercises the page-loop contract in
  `fetch_ohlcv(..., start, end)`.
- **Sparse/no-tick interval handling:** Omitted intervals test
  whether row counts match expected partition size.
- **Missing interval classification:** First real data where
  "gap" is a normal property, not a bug.
- **Timeframe mapping:** Different symbol → interval conventions
  from Bitfinex.
- **Provider-specific response parsing:** Different JSON envelope,
  different error signalling.

**Expected use after Bitfinex:**
- Test how validation handles omitted no-trade intervals.
- Test provider-specific completeness assumptions.
- Compare behaviour against Bitfinex.

**Caveats:**
- Kline data may be incomplete for low-volume pairs.
- No-tick intervals may be omitted entirely.
- This makes it useful for validation but more nuanced than
  Bitfinex — the validation layer must tolerate gaps rather
  than flagging them as errors.

---

### 3. Bybit — Third Provider

**Access:**
- Cost: Free
- Sign-up required: No
- API key required for public klines: No

**Why ranked third:**
- Public kline endpoint with `category` parameter (spot, linear,
  inverse).
- Up to 1,000 candles per call.
- Good third-provider comparison once the validation layer is
  stable against Bitfinex and KuCoin.

**Validation value:**
- **Multi-category dispatch:** The provider adapter must route
  based on `category` — tests adapter design flexibility.
- **Different response envelope:** Yet another JSON structure
  to parse — confirms the `MarketDataProvider` interface is
  general enough.
- **Third behaviour baseline:** Two data points (Bitfinex, KuCoin)
  may reveal a pattern; three starts to prove it.

**Expected use:**
- Confirm that the provider adapter pattern generalises beyond
  two implementations.
- Test validation-layer tolerance for a third set of timestamp
  and interval conventions.

**Caveats:**
- Marginally higher integration friction than Bitfinex due to
  the `category` routing parameter.
- Rate limits are per-category, adding a minor complication.

---

## Kraken — Not in Top 3; Use as Edge-Case Test Later

**Why Kraken is not ranked higher despite being free and public:**
- **720 committed candles per call** — the smallest page size
  of any major exchange. Reaching 10,000 candles requires ~14
  pages, making initial integration slower to debug.
- **Partial current candle in every response** — adds complexity
  that provides no validation value until the stripping logic is
  already tested elsewhere.
- **Symbol naming is non-intuitive** (`XXBTZUSD` instead of
  `BTC/USD` or `XBTUSD`) — more mapping overhead for the first
  provider.
- **Rate limit of 1 req/3s per pair** — backfill is noticeably
  slow, making iteration cycles painful during development.

**Where Kraken does add unique value (used later):**
- Testing the pagination loop with the **max page count for a
  given date range** (most pages per partition = most stress on
  page accumulation logic).
- Testing **partial candle stripping** — ensuring the last entry
  is correctly removed before validation.
- Testing **rate-limit compliance** in the backfill loop.
- Testing symbol-mapping edge cases (`XBT` vs `BTC`, multi-asset
  pairs like `XBT/EUR`, fiat pairs).

## Summary — Provider Adoption Sequence

| Step | Provider | Why | Validation stress |
|---|---|---|---|
| 1 | **Bitfinex** | Large batch, deep history, no auth | Batch size, partitions, append, scale |
| 2 | **KuCoin** | Sparse interval behaviour | Pagination, completeness, gaps |
| 3 | **Bybit** | Multi-category, third baseline | Interface generality |
| 4+ | **Kraken** | Constrained page, partial candle | Pagination loop, edge-case checks |
| 5+ | Other (Binance, Coinbase) | Market coverage | — |

## Key Principle

Do not treat shallow data providers as automatically better for
validation. The most valuable validation provider is the one that
returns the most data with the least friction — it lets you stress
the entire ingestion, validation, storage, and benchmark pipeline
end-to-end in a single call. Constrained providers are added later
as targeted edge-case tests against infrastructure already proven
at scale.
