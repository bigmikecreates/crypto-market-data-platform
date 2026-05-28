# Providers

## Provider Contract

All providers implement `OHLCVProvider` (`providers/base.py`):

```python
class OHLCVProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]: ...
```

The contract is intentionally minimal. Each adapter absorbs API-specific
differences — URL scheme, authentication, field ordering, pagination,
rate limits — behind this single method.

## Supported Providers

| Provider | Class | Status | Batch Limit | Field Order |
|----------|-------|--------|-------------|-------------|
| Fake | `FakeProvider` | Stable | 1 | Standard |
| Bitfinex | `BitfinexProvider` | Stable | 10,000 | Non-standard: `[MTS, OPEN, CLOSE, HIGH, LOW, VOL]` |
| KuCoin | `KuCoinProvider` | Stable | 1,500 | Standard: `[time, open, close, high, low, volume, turnover]` |
| Bybit | — | Planned (#2) | — | — |
| Kraken | — | Planned (#3) | — | — |

### FakeProvider

Returns a single pre-calculated candle (and funding rate) for testing and
benchmarking. No network access. All numeric fields are hardcoded strings.

### BitfinexProvider

- URL: `https://api-pub.bitfinex.com/v2/candles/trade:{tf}:{sym}/hist`
- Requires a `Mozilla/5.0` User-Agent header (default Python `urllib`
  User-Agent is blocked by Cloudflare)
- Field order is non-standard: `[MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]`
  — the `_parse_row()` method remaps to canonical ordering
- Pagination uses `end` parameter (millisecond timestamps), standard REST
  cursor pattern
- `_MAX_LIMIT = 10000` allows large batch sizes, reducing round-trips

### KuCoinProvider

- URL: `https://api.kucoin.com/api/v1/market/candles/{sym}`
- Timestamps are in **seconds**, not milliseconds — `int(row[0])` not
  `/ 1000`
- Error reporting via HTTP 200 with embedded `code` field in JSON body,
  not HTTP 4xx/5xx
- Batch limit is server-enforced at 1500 (no `limit` parameter is sent;
  the limit is detected by `len(rows) < 1500`)
- Response includes a `turnover` field that is discarded — it represents
  base-volume in KuCoin's response format and is not part of the
  canonical `Candle` model

## Adding a New Provider

1. Create `providers/{name}.py` with a class implementing
   `OHLCVProvider`
2. Define symbol and timeframe mappers (`_to_{name}_symbol()`,
   `_to_{name}_timeframe()`)
3. Implement `_parse_row()` to convert raw API row → `Candle`
4. Implement `fetch_ohlcv()` with pagination loop
5. Register the provider in `cli/main.py`'s `PROVIDERS` dict
6. Add fixture-based tests in `tests/providers/` (no live network access)
7. Document symbol mappings and timestamp semantics

See `docs/lessons-from-bitfinex-integration.md` and
`docs/lessons-from-kucoin-integration.md` for detailed case studies.
