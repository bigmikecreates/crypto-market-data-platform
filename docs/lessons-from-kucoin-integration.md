# Lessons from the KuCoin Provider Integration

## Architecture Validation — What Worked as Designed

These confirm that the architecture decisions made during the planning
phase held up under real-world data.

### 1. The provider adapter pattern absorbed KuCoin's differences cleanly

KuCoin differs from the Bitfinex model in several ways:

- Different API response envelope (`{"code": "200000", "data": [...]}`
  vs raw array)
- Seconds-precision timestamps (Bitfinex uses milliseconds)
- Smaller max batch (1500 vs 10000)
- Standard field order `[time, open, close, high, low, volume, turnover]`
  (no field-ordering surprise)
- Hyphen-separated symbols (`BTC-USDT` vs `tBTCUSD`)
- Different timeframe labels (`1hour` vs `1h`)

Every difference was handled inside `providers/kucoin.py`. No changes
were needed to `Candle`, validation, or the writer. This confirms that
the provider boundary design generalises beyond a single exchange.

### 2. Pre-emptive User-Agent header avoids WAF issues

Based on the Bitfinex lesson, the same `Mozilla/5.0...` User-Agent
string was included from the first commit. The live test passed on
the first attempt — no Cloudflare block.

**Takeaway:** The User-Agent fix from Bitfinex is a portable solution.
Future providers should include the same header preemptively rather
than discovering the issue at test time.

### 3. Validation rules remain at zero false positives

48 real 1h candles from KuCoin passed with 0 issues. No rule adjustment
was needed for this provider either — the same 5 provider-independent
rules (EMPTY_FIELD, INVALID_DECIMAL, INVALID_TIMESTAMP, OHLC_INVARIANT,
DUPLICATE_TIMESTAMP) work correctly across two different exchanges.

### 4. Seconds timestamps are handled transparently

KuCoin returns unix timestamps in seconds (`int(row[0])`), not
milliseconds like Bitfinex (`int(row[0]) / 1000`). Both convert to the
same ISO-8601 string format via `datetime.fromtimestamp(...)`. The
`Candle.timestamp` string field absorbs this difference — no schema
change needed.

### 5. Standard field order reduces adapter risk

KuCoin's response order `[time, open, close, high, low, volume, turnover]`
matches the industry standard, unlike Bitfinex's non-standard
`[MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]`. The adapter was simpler to
write and required less cross-referencing with the docs. This confirms
that Bitfinex was the right first choice (hardest case first).

---

## Lessons Learned — What the Implementation Revealed

### 1. The turnover field is present but can be safely ignored

KuCoin returns a 7th field (`turnover`, in quote currency) that is not
part of the `Candle` model. The adapter simply ignores it (row indexing
stops at `volume=row[5]`). This is fine — no need to extend the model
for provider-specific extra fields.

**Action for future providers:** Expect extra trailing fields in some
responses. They can be silently ignored as long as the required fields
are present at known indices.

### 2. No partial candle on the current period

Like Bitfinex (and unlike Kraken), KuCoin returns only fully-closed
candles. The 48 candles from a 2-day window are exactly `2 * 24 = 48`,
confirming no partial candle is included. No stripping logic needed.

**Action for future providers:** Verify partial-candle behaviour
empirically. Do not assume either behaviour from documentation alone.

### 3. Pagination not exercised at typical ranges

With `limit=1500`, a 2-day window at 1h granularity (48 candles)
fits comfortably in one page. Pagination would only activate at fine
granularity (e.g., multiple days of 1m data producing 1440+ candles).
The untiled code path is exercised only in edge cases.

**Takeaway:** Same behaviour as Bitfinex (10000 limit) — pagination
exists for robustness, not daily use. Test explicitly with a wide
date range at 1m granularity if pagination confidence is needed.

### 4. Error code checking is different from Bitfinex

KuCoin returns HTTP 200 with a `code` field inside the JSON body
(e.g., `"400001"` for invalid symbol), while Bitfinex returns actual
HTTP 4xx/5xx status codes. The error-handling pattern was copied from
Bitfinex but had to be adapted to check `data.get("code") != "200000"`
on every response instead of catching HTTPError exceptions.

**Action for future providers:** Verify the error-reporting mechanism
for each provider during implementation. Do not assume HTTP status
codes are reliable — some providers return 200 with embedded errors.

### 5. KuCoin's response envelope is always an object

Unlike Bitfinex (which returns a bare array `[[...], [...]]`), KuCoin
always wraps data in `{"code": "200000", "data": [...]}`. The adapter
must decode the JSON object and extract `data["data"]` rather than
returning the raw parsed JSON directly.

**Takeaway:** Response envelope differences are handled inside the
provider adapter. No general-purpose response parsing layer is needed
— each provider's `_fetch_ohlcv_page` method owns the full HTTP-to-data
transformation.

### 6. 1500-limit batch is visible in the request URL

KuCoin does not accept a `limit` parameter — the 1500-candle maximum
is enforced server-side. The adapter simply requests all available
data within the time window and relies on `len(rows) < 1500` to detect
the last page. This is simpler than Bitfinex's explicit `limit=10000`
parameter approach.

**Action for future providers:** Document whether the max batch size
is parameterised (like Bitfinex's `limit=10000`) or server-enforced
(like KuCoin's implicit 1500). This affects how the adapter detects
the final page.
