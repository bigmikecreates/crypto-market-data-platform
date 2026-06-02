# Python API Reference

---

## `crmd_platform.providers`

Providers implement `OHLCVProvider` (candle data) or `FundingRateProvider` (funding rates). The import paths support both.

### Import

```python
from crmd_platform.providers import (
    BitfinexProvider, BitstampProvider, BybitProvider,
    FakeProvider, KuCoinProvider, MexcProvider,
)
from crmd_platform.providers.base import FundingRateProvider
```

### `OHLCVProvider`

Abstract base class for all providers.

#### Usage

```python
class OHLCVProvider(ABC):
    def fetch_ohlcv(
        self, symbol: str, timeframe: str,
        start: datetime, end: datetime,
    ) -> list[Candle]: ...
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `symbol` | `str` | Trading pair symbol (e.g. `"BTC/USDT"`) |
| `timeframe` | `str` | Candle interval (e.g. `"1h"`, `"1d"`) |
| `start` | `datetime` | Start of range (inclusive) |
| `end` | `datetime` | End of range (exclusive) |

### `FakeProvider`

Synthetic data provider for testing. Also exposes `fetch_funding_rates`.

#### Usage

```python
provider = FakeProvider()
candles = provider.fetch_ohlcv("BTC/USDT", "1h", start, end)
rates = provider.fetch_funding_rates("BTC/USDT", start, end)
```

#### Examples

```python
>>> from crmd_platform.providers import FakeProvider
>>> from datetime import datetime, timezone
>>> p = FakeProvider()
>>> candles = p.fetch_ohlcv("BTC/USDT", "1h",
...     datetime(2026, 5, 27, tzinfo=timezone.utc),
...     datetime(2026, 5, 28, tzinfo=timezone.utc))
>>> len(candles)
1
```

### Provider details

#### `BitfinexProvider`

```python
class BitfinexProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = 0.15) -> None: ...
```

| Property | Value |
|----------|-------|
| URL | `https://api-pub.bitfinex.com/v2/candles/trade:{tf}:{sym}/hist` |
| Field order | `[MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]` (non-standard) |
| Max limit | 10 000 |
| Sort | `sort=1` (ascending) |
| Symbol mapping | `BTC/USD` → `tBTCUSD` |
| Timeframe mapping | `1h` → `1h`, `1d` → `1D`, `1w` → `1W`, `14d` → `14D` |
| User-Agent | Required (Cloudflare WAF) |

#### `BitstampProvider`

```python
class BitstampProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = 0.05) -> None: ...
```

| Property | Value |
|----------|-------|
| URL | `https://www.bitstamp.net/api/v2/ohlc/{sym}/` |
| Response format | Dict rows with keys `timestamp`, `open`, `high`, `low`, `close`, `volume` |
| Step map | `1m` → 60, `1h` → 3600, `1d` → 86400 (seconds-based) |

#### `BybitProvider`

```python
class BybitProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = 0.2) -> None: ...
```

| Property | Value |
|----------|-------|
| URL | `https://api.bybit.com/v5/market/kline` |
| Category | `spot` |
| Field order | `[timestamp, open, high, low, close, volume]` |
| Max limit | 1000 |
| Sort | Descending (requires `.reverse()`) |
| Error check | `data.get("retCode") != 0` |

#### `KuCoinProvider`

```python
class KuCoinProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = 0.1) -> None: ...
```

| Property | Value |
|----------|-------|
| URL | `https://api.kucoin.com/api/v1/market/candles?symbol={sym}` |
| Field order | `[time, open, close, high, low, volume, turnover]` (standard + turnover) |
| Max limit | 1500 (server-enforced, no `limit` param) |
| Timestamps | Seconds (`int(row[0])`) |
| Error reporting | HTTP 200 with `code` field in JSON body |

#### `MexcProvider`

```python
class MexcProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = 0.05) -> None: ...
```

| Property | Value |
|----------|-------|
| URL | `https://api.mexc.com/api/v3/klines` |
| Field order | `[timestamp, open, high, low, close, volume]` |
| Max limit | 500 |
| Error check | Response must be a list; dict response raises `RuntimeError` |

---

## `crmd_platform.models`

Data model classes.

### Import

```python
from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
```

### Models

| Model | Fields |
|-------|--------|
| `Candle` | `exchange`, `symbol`, `timeframe`, `timestamp`, `open`, `high`, `low`, `close`, `volume`, `source` |
| `FundingRate` | `exchange`, `symbol`, `timestamp`, `rate`, `predicted_rate`, `next_funding_time`, `source` |

All fields are `str`. Numeric values are parsed and cast at write time.

---

## `crmd_platform.validation`

Batch validation functions.

### Import

```python
from crmd_platform.validation import (
    validate_candle_batch,
    validate_funding_rate_batch,
    ValidationIssue,
    ValidationResult,
)
```

### `validate_candle_batch`

Validates a batch of candles. Returns all issues (non-fail-fast).

#### Usage

```python
result = validate_candle_batch(candles)
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `candles` | `list[Candle]` | Candle batch to validate |

#### Examples

```python
>>> from crmd_platform.validation import validate_candle_batch
>>> from crmd_platform.models.candle import Candle
>>> candles = [Candle("fake", "BTC/USDT", "1h", "2026-05-27T00:00:00",
...     "100", "110", "90", "105", "10", "fake")]
>>> result = validate_candle_batch(candles)
>>> result.passed
True
```

### `validate_funding_rate_batch`

Validates a batch of funding rates.

#### Usage

```python
result = validate_funding_rate_batch(rates)
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `rates` | `list[FundingRate]` | Funding rate batch to validate |

### Data structures

| Class | Fields |
|-------|--------|
| `ValidationIssue` | `severity: str`, `code: str`, `message: str`, `candle_index: int \| None`, `field: str \| None` |
| `ValidationResult` | `passed: bool`, `issues: list[ValidationIssue]` |

### Helper functions

```python
def decimal_gte(a: str, b: str) -> bool:
    """String-based decimal comparison. Compares integer parts with length-aware
    padding, zero-pads fractional parts. No Decimal objects created."""

def digit_count(s: str) -> int:
    """Counts significant digits in a decimal string (excludes '.')."""
```

### Regex patterns

```python
SIGNED_DECIMAL_PATTERN = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
UNSIGNED_DECIMAL_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)?$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$")
```

See [Validation Rules](validation-rules.md) for the full rule catalogue.

---

## `crmd_platform.storage`

Low-level write functions. Prefer `OHLCVService` / `FundingRateService` for normal use.

### Import

```python
from crmd_platform.storage.parquet_writer import (
    candle_to_table,
    funding_rate_to_table,
    write_candles,
    write_funding_rates,
)
```

### Constants

```python
DECIMAL128_TYPE = pa.decimal128(38, 10)
ROW_MERGE_THRESHOLD = 50_000
CANDLE_KEY_COLS = ["exchange", "symbol", "timeframe", "source", "timestamp"]
FUNDING_RATE_KEY_COLS = ["exchange", "symbol", "source", "timestamp"]
```

### `candle_to_table`

Converts `Candle` objects to a PyArrow Table with decimal128 and timestamp casts.

#### Usage

```python
table = candle_to_table(candles, ts_config)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `candles` | `list[Candle]` | required | Candle objects to convert |
| `ts_config` | `TimestampConfig` | required | Timestamp resolution configuration |

### `funding_rate_to_table`

Converts `FundingRate` objects to a PyArrow Table.

#### Usage

```python
table = funding_rate_to_table(rates, ts_config)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rates` | `list[FundingRate]` | required | Funding rate objects to convert |
| `ts_config` | `TimestampConfig` | required | Timestamp resolution configuration |

### `write_candles`

Groups candles by partition, merges with existing files, writes Parquet.

#### Usage

```python
paths = write_candles(candles, base_path="data", ts_config=None, merge_strategy="auto")
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `candles` | `list[Candle]` | required | Candle batch to write |
| `base_path` | `str` | `"data"` | Base output directory |
| `ts_config` | `TimestampConfig \| None` | `None` | Timestamp resolution (defaults to second resolution) |
| `merge_strategy` | `str` | `"auto"` | Row merge strategy: `"auto"`, `"memory"`, or `"duckdb"` |

### `write_funding_rates`

Groups funding rates by partition, merges with existing files, writes Parquet.

#### Usage

```python
paths = write_funding_rates(rates, base_path="data", ts_config=None, merge_strategy="auto")
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rates` | `list[FundingRate]` | required | Funding rate batch to write |
| `base_path` | `str` | `"data"` | Base output directory |
| `ts_config` | `TimestampConfig \| None` | `None` | Timestamp resolution (defaults to second resolution) |
| `merge_strategy` | `str` | `"auto"` | Row merge strategy: `"auto"`, `"memory"`, or `"duckdb"` |

### Merge functions

```python
def merge_via_set(
    existing: pa.Table, incoming: pa.Table,
    key_cols: list[str],
) -> pa.Table:
    """In-memory set-based merge. Builds set of existing row keys,
    filters incoming to rows not in existing, concatenates."""

def merge_via_duckdb(
    existing: pa.Table, incoming: pa.Table,
    key_cols: list[str],
) -> pa.Table:
    """DuckDB ANTI JOIN + UNION ALL merge. Best for large tables."""

def merge_tables(
    existing: pa.Table, incoming: pa.Table,
    key_cols: list[str],
    strategy: str = "auto",
) -> pa.Table:
    """Dispatches to merge_via_set or merge_via_duckdb based on strategy and row count."""
```

### Type cast functions

```python
def to_decimal128(
    values: list[str], label: str, candle_key: str,
) -> pa.Array:

def to_timestamp(
    values: list[str], ts_config: TimestampConfig,
) -> pa.Array:
```

### Merge strategies (`merge_strategy`)

| Strategy | Behaviour |
|----------|-----------|
| `auto` | Uses DuckDB merge for batches ≥50 000 rows, in-memory set merge otherwise |
| `memory` | Always use in-memory set-based merge (loads both tables fully) |
| `duckdb` | Always use DuckDB SQL `ANTI JOIN` + `UNION ALL` merge |

### Partition layout

```
data/{exchange}/{symbol}/{timeframe}/{date}.parquet        # candles
data/{exchange}/{symbol}/funding_rate/{date}.parquet       # funding rates
```

### Path helpers

```python
def path_for_candle(c: Candle, base_path: str) -> Path: ...
def path_for_funding_rate(r: FundingRate, base_path: str) -> Path: ...
```

See [Parquet Schema](parquet-schema.md) for the full column type mapping.

---

## `crmd_platform.ingestion`

High-level ingestion services that combine fetching, validation, and storage.

### Import

```python
from crmd_platform.ingestion import OHLCVService, FundingRateService
```

### `OHLCVService`

#### Usage

```python
service = OHLCVService(provider, ts_config=None)
count = service.ingest(symbol, timeframe, start, end, base_path="data", merge_strategy="auto")
```

#### Parameters — constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | `OHLCVProvider` | required | Provider instance for fetching data |
| `ts_config` | `TimestampConfig \| None` | `None` | Timestamp resolution configuration |

#### Parameters — `ingest`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | `str` | required | Trading pair symbol |
| `timeframe` | `str` | required | Candle interval |
| `start` | `datetime` | required | Start of range (inclusive) |
| `end` | `datetime` | required | End of range (exclusive) |
| `base_path` | `str` | `"data"` | Base output directory |
| `merge_strategy` | `str` | `"auto"` | Row merge strategy |

#### Examples

```python
>>> from crmd_platform.ingestion import OHLCVService
...
>>> service = OHLCVService(FakeProvider())
>>> count = service.ingest("BTC/USDT", "1h",
...     datetime(2026, 5, 27, tzinfo=timezone.utc),
...     datetime(2026, 5, 28, tzinfo=timezone.utc))
>>> count
1
```

### `FundingRateService`

#### Usage

```python
service = FundingRateService(provider, ts_config=None)
count = service.ingest(symbol, start, end, base_path="data", merge_strategy="auto")
```

#### Parameters — constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | `FundingRateProvider` | required | Provider instance for fetching funding rates |
| `ts_config` | `TimestampConfig \| None` | `None` | Timestamp resolution configuration |

#### Parameters — `ingest`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | `str` | required | Trading pair symbol |
| `start` | `datetime` | required | Start of range (inclusive) |
| `end` | `datetime` | required | End of range (exclusive) |
| `base_path` | `str` | `"data"` | Base output directory |
| `merge_strategy` | `str` | `"auto"` | Row merge strategy |

---

## `crmd_platform.query`

Query interface for stored datasets.

### Import

```python
from crmd_platform.query import QueryService, DuckDBQueryService
```

### `QueryService`

Abstract base class.

#### Usage

```python
class QueryService(ABC):
    def list_datasets(self, base_path: str = "data") -> dict[str, list[str]]: ...
    def get_candles(self, base_path: str = "data", exchange: str | None = None,
        symbol: str | None = None, timeframe: str | None = None,
        start: str | None = None, end: str | None = None,
        limit: int = 100, order: str = "DESC") -> list[Candle]: ...
    def get_funding_rates(self, base_path: str = "data",
        exchange: str | None = None, symbol: str | None = None,
        start: str | None = None, end: str | None = None,
        limit: int = 100, order: str = "DESC") -> list[FundingRate]: ...
    def get_summary(self, base_path: str = "data") -> list[dict[str, Any]]: ...
    def raw_sql(self, sql: str, base_path: str = "data") -> list[dict[str, Any]]: ...
```

### `DuckDBQueryService`

Implementation backed by DuckDB `read_parquet`.

#### Usage

```python
qs = DuckDBQueryService()
datasets = qs.list_datasets()
candles = qs.get_candles(exchange="bitfinex", limit=5)
```

#### Examples

```python
>>> from crmd_platform.query import DuckDBQueryService
>>> qs = DuckDBQueryService()
>>> qs.list_datasets()
{'candle': ['bitfinex/BTC/USD/1h']}
```

### Internal helpers

```python
def _discover_files(base_path: str) -> dict[str, dict[str, list[Path]]]:
    """Returns {"candle": {"exchange/symbol/timeframe": [Paths]},
                "funding_rate": {"exchange/symbol/funding_rate": [Paths]}}"""

def _rows_to_dicts(sql_result: Any) -> list[dict[str, Any]]:
    """Converts DuckDB result rows to dicts, normalising Decimal→str
    and datetime→ISO-8601."""

@staticmethod
def DuckDBQueryService._resolve_files(
    base_path: str, data_type: str,
    exchange: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
) -> list[Path]: ...

@staticmethod
def DuckDBQueryService._build_query(
    files: list[Path],
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
    order: str = "DESC",
) -> str: ...
```

---

## `crmd_platform.config`

Configuration types.

### Import

```python
from crmd_platform.config import TimestampConfig
```

### `TimestampConfig`

#### Usage

```python
config = TimestampConfig(resolution="s")
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resolution` | `str` | `"s"` | Timestamp resolution: `"s"` (seconds) or `"us"` (microseconds) |

Computed properties:

| Property | `"s"` (default) | `"us"` |
|----------|-----------------|--------|
| `format` | `"%Y-%m-%dT%H:%M:%S"` | `"%Y-%m-%dT%H:%M:%S.%f"` |
| `parquet_type` | `pa.timestamp("s")` | `pa.timestamp("us")` |

---

## `crmd_platform.server`

REST server factory and configuration.

### Import

```python
from crmd_platform.server import create_app
from crmd_platform.server.config import ServerConfig
```

### `create_app`

Factory function. Creates FastAPI app with all routers mounted.

#### Usage

```python
app = create_app(config)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `ServerConfig \| None` | `None` | Server configuration (uses defaults if `None`) |

### `ServerConfig`

#### Usage

```python
config = ServerConfig(host="127.0.0.1", port=8000, base_path="data")
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"127.0.0.1"` | Bind address |
| `port` | `int` | `8000` | Bind port |
| `base_path` | `str` | `"data"` | Base data directory |
| `query_service` | `QueryService` | `DuckDBQueryService()` | Query service instance |

### App behaviour

- Injects `query_service` and `base_path` into `app.state`.
- Adds `CORSMiddleware` (allow all origins/methods/headers).
- Adds global exception handler returning `{"error": <msg>, "code": 500}`.
- Includes 6 routers: health, datasets, candles, funding, query, summary.

---

## `crmd_platform.benchmark`

Performance benchmark tooling.

### Import

```python
from crmd_platform.benchmark import (
    BenchmarkContext, BenchmarkResult, CandlePipelineRunner,
    CrossValidationRule, PipelineRunner, ProviderCandlePipelineRunner,
    RUNNERS, StageMetrics, evaluate_rules,
)
```

### `PipelineRunner`

Abstract base class for benchmark runners.

#### Usage

```python
class PipelineRunner(ABC):
    def run_coarse(self, count: int, ts_config: TimestampConfig,
        base_path: str) -> BenchmarkResult: ...
    def run_verbose(self, count: int, ts_config: TimestampConfig,
        base_path: str) -> BenchmarkResult: ...
```

### `CandlePipelineRunner`

Synthetic benchmark: creates `Candle` objects → table → write → read.

#### Usage

```python
runner = CandlePipelineRunner()
result = runner.run_coarse(count=1000, ts_config=ts_config, base_path="/tmp/bench")
```

### `ProviderCandlePipelineRunner`

Live provider benchmark: fetches real candles → validate → write → read.

#### Usage

```python
runner = ProviderCandlePipelineRunner(
    provider=BitfinexProvider(),
    symbol="BTC/USD",
    timeframe="1h",
    start=datetime(2026, 1, 1, tzinfo=timezone.utc),
    end=datetime(2026, 1, 2, tzinfo=timezone.utc),
)
result = runner.run_coarse(count=1, ts_config=ts_config, base_path="/tmp/bench")
```

#### Parameters — constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | `OHLCVProvider` | required | Provider to benchmark |
| `symbol` | `str` | `"BTC/USDT"` | Trading pair symbol |
| `timeframe` | `str` | `"1h"` | Candle interval |
| `start` | `datetime \| None` | `None` | Start of range |
| `end` | `datetime \| None` | `None` | End of range |

### Dataclasses

| Class | Fields |
|-------|--------|
| `StageMetrics` | `name: str`, `wall_ms: float`, `cpu_ms: float`, `mem_delta_mb: float`, `peak_mb: float`, `gc_g0: int`, `gc_g1: int`, `gc_g2: int`, `file_kb: float \| None` |
| `BenchmarkResult` | `count: int`, `ts_resolution: str`, `runner_name: str`, `stages: list[StageMetrics]`, `schema: dict[str, str]`, `pipeline_end_index: int`, `validation_issues: int` |
| `BenchmarkContext` | `checkpoint(name, file_kb)`, `total_mem_delta_mb` |
| `CrossValidationRule` | `name: str`, `evaluate: Callable[[BenchmarkResult], tuple[str, str]]`, `recommendation: str \| None` |

```python
RUNNERS: dict[str, type[PipelineRunner]] = {
    "candle": CandlePipelineRunner,
    "provider": ProviderCandlePipelineRunner,
}

def evaluate_rules(
    rules: list[CrossValidationRule],
    result: BenchmarkResult,
) -> list[tuple[str, str, str]]:
    """Returns list of (rule_name, rating, message) tuples."""
```

---

## `crmd_platform.utils`

Utility functions.

### Import

```python
from crmd_platform.utils.parquet_viewer import run_inspect
```

### `run_inspect`

Inspect a Parquet file or directory. Returns formatted text output.

#### Usage

```python
output = run_inspect(path_str, limit=10, start=None, end=None,
    show_stats=False, show_verbose=False)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path_str` | `str` | required | Path to a `.parquet` file or dataset directory |
| `limit` | `int` | `10` | Max rows in sample output |
| `start` | `str \| None` | `None` | Start of timestamp range (inclusive), ISO-8601 |
| `end` | `str \| None` | `None` | End of timestamp range (exclusive), ISO-8601 |
| `show_stats` | `bool` | `False` | Show column statistics |
| `show_verbose` | `bool` | `False` | Show full Parquet metadata |

---

← [API Reference Overview](overview.md)
