# Providers

## Provider Contract

Each provider adapter implements `OHLCVProvider` — an abstract base
class with a single method `fetch_ohlcv()`. The contract is intentionally
minimal. Each adapter absorbs API-specific differences (URL scheme,
authentication, field ordering, pagination, rate limits) behind this
interface.

## Supported Providers

| Provider | Status | Notes |
|----------|--------|-------|
| `FakeProvider` | Stable | Returns pre-calculated candles and funding rates. No network access. |
| `BitfinexProvider` | Stable | Large batch limit (10,000), non-standard field order. |
| `BitstampProvider` | Stable | Dict-based response format. |
| `KuCoinProvider` | Stable | Seconds timestamps, server-enforced batch limit (1,500). |
| `BybitProvider` | Stable | Category-based dispatch (spot). Descending sort order. |
| `MexcProvider` | Stable | Standard field order, 500-candle limit. |

## Adding a New Provider

See [Python API Reference](/crypto-market-data-platform/reference/#/python-api) for exact provider signatures, URL
endpoints, field orders, symbol mappings, rate limits, and pagination
details.

See `docs/lessons-from-bitfinex-integration.md` and
`docs/lessons-from-kucoin-integration.md` for detailed case studies on
what real provider integrations revealed.
