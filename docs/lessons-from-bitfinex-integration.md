# Lessons from the Bitfinex Provider Integration

## Architecture Validation — What Worked as Designed

These confirm that the architecture decisions made during the planning
phase held up under real-world data.

### 1. Four OHLC invariant checks caught a field-ordering bug

Bitfinex returns candle data in non-standard order (close before high).
During initial adapter development, an incorrect field mapping would have
assigned the close price to the high field. The `high >= open` invariant would have failed
on the very first candle — immediately signalling a parsing problem
rather than silently writing corrupted data.

The 4 invariant checks (`high >= open`, `high >= close`,
`low <= open`, `low <= close`) proved to be a safety net for adapter
bugs, not a theoretical exercise.

### 2. Provider boundary absorbed all exchange-specific mess

Bitfinex differs from the canonical model in several ways:

- Millisecond timestamps (model uses ISO-8601 strings)
- Non-standard field order in response arrays
- Different symbol conventions (`tBTCUSD` vs `BTC/USD`)
- Different timeframe labels (`1D` vs `1d`, `14D` vs `14d`)

Every difference was handled inside the provider adapter. The `Candle`
model, validation layer, and writer were not modified. This confirms
that the provider boundary design (raw response → canonical `Candle`)
is correctly scoped.

### 3. Validation rules produced zero false positives

48 real 1h candles from a production exchange passed validation with
0 issues across all 5 provider-independent rules. No rule needed
softening, removal, or threshold adjustment. The calibration of
EMPTY_FIELD, INVALID_DECIMAL, INVALID_TIMESTAMP, OHLC_INVARIANT, and
DUPLICATE_TIMESTAMP is correct for production data.

### 4. Large batch limit simplifies the pagination loop

Bitfinex supports `limit=10000` per call. For typical date ranges
at 1h granularity, a single page covers the entire range. Pagination
only activates for wide ranges at fine granularity (e.g., multiple
weeks of 1m data). This means the pagination logic exists mainly for
edge-case robustness rather than day-to-day use, which kept the
initial implementation straightforward.

### 5. Both symbol formats work as expected

The provider accepts both canonical (`BTC/USD`) and native
(`tBTCUSD`) symbols. The canonical path strips `/`, uppercases,
and prepends `t`. The native path passes through unchanged. Both
routes produce identical candle objects.

---

## Lessons Learned — What the Implementation Revealed

These are findings that no amount of planning or fake data could
have surfaced. They should inform future provider integrations.

### 1. Real API calls reveal infrastructure issues that fixtures cannot

The first live request was blocked by Cloudflare (Error 1010) because
Python's default `urllib.request` User-Agent is flagged by Bitfinex's
WAF. This required adding an explicit `User-Agent` header with a
realistic browser string before the API would respond.

No fixture-based test would ever catch this. Every provider adapter
must be tested with a live API call at least once during development
to uncover transport-layer issues (WAF blocks, DNS resolution, TLS
version incompatibilities, redirect handling, rate-limit headers).

→ See [Python API Reference](/crypto-market-data-platform/reference/#/python-api) for the exact
field order and URL details for each provider.

### 2. Bitfinex's field ordering is non-standard and poorly documented

The response format `[MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]` places
`CLOSE` before `HIGH` and `LOW`, unlike the industry-standard
`[timestamp, open, high, low, close, volume]`. This is a known
Bitfinex quirk that is not prominently called out in their API docs.

→ See [Python API Reference](/crypto-market-data-platform/reference/#/python-api) for the exact
field positions for each provider.

### 3. Symbol mapping is not trivially automatable

Simple transforms (`BTC/USD` → `tBTCUSD`) work for USD pairs, but
USDT pairs require different handling (`BTC/USDT` → `tBTCUST`, where
`UST` is Bitfinex's native code for USDT). A general-purpose symbol
normaliser would require a full mapping table for every exchange.

→ See [Python API Reference](/crypto-market-data-platform/reference/#/python-api) for symbol
mapping details per provider.

### 4. Rate-limit behaviour requires empirical verification

Bitfinex's rate limit is documented as 10 requests per second, but
the actual enforcement behaviour (burst allowance, sliding window,
penalty duration) can only be determined empirically. A
`rate_limit_sleep` parameter with a configurable default allows
tuning without code changes.

→ See [Python API Reference](/crypto-market-data-platform/reference/#/python-api) for rate-limit
configuration per provider.

### 5. The last candle in a Bitfinex response may be incomplete

Unlike Kraken (which always includes a partial current candle),
Bitfinex returns only fully-closed candles within the requested
time range. This was verified empirically — no candle stripping
logic is needed.

*Action for future providers:* Do not assume the presence or
absence of a partial candle. Empirically verify each provider's
behaviour during implementation and document it in the adapter.

### 6. Fixture-based tests catch parsing bugs but not transport bugs

The fixture-based test suite confirms that the adapter correctly
parses known-good JSON into `Candle` objects. This is valuable for:
- Regression testing after code changes
- CI environments without external network access
- Verifying field mapping correctness

However, fixtures do not cover:
- Transport-layer failures (WAF blocks, DNS, TLS)
- HTTP error responses with non-JSON bodies
- Rate-limit enforcement
- Empty responses for valid but data-less ranges
- Partial or truncated responses

*Action for future providers:* Maintain both fixture-based tests
(for CI) and a separate manual smoke test script (for development)
that makes real API calls and prints the results.
