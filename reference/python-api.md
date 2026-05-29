# Python API Reference

## `crypto_market_data_platform.providers`

```python
from crypto_market_data_platform.providers import (
    BitfinexProvider, BitstampProvider, BybitProvider,
    FakeProvider, KuCoinProvider, MexcProvider,
)
```

All providers implement the abstract base class:

```python
class OHLCVProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self, symbol: str, timeframe: str,
        start: datetime, end: datetime,
    ) -> list[Candle]: ...
```

`FakeProvider` also exposes:

```python
class FakeProvider(OHLCVProvider):
    def fetch_funding_rates(
        self, symbol: str,
        start: datetime, end: datetime,
    ) -> list[FundingRate]: ...
```

### Provider details

#### BitfinexProvider

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

#### BitstampProvider

```python
class BitstampProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = 0.05) -> None: ...
```

| Property | Value |
|----------|-------|
| URL | `https://www.bitstamp.net/api/v2/ohlc/{sym}/` |
| Response format | Dict rows with keys `timestamp`, `open`, `high`, `low`, `close`, `volume` |
| Step map | `1m` → 60, `1h` → 3600, `1d` → 86400 (seconds-based) |

#### BybitProvider

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

#### KuCoinProvider

```python
class KuCoinProvider(OHLCVProvider):
    def __init__(self, rate_limit_sleep: float = 0.1) -> None: ...
```

| Property | Value |
|----------|-------|
| URL | `https://api.kucoin.com/api/v1/market/candles/{sym}` |
| Field order | `[time, open, close, high, low, volume, turnover]` (standard + turnover) |
| Max limit | 1500 (server-enforced, no `limit` param) |
| Timestamps | Seconds (`int(row[0])`) |
| Error reporting | HTTP 200 with `code` field in JSON body |

#### MexcProvider

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

## `crypto_market_data_platform.models`

```python
from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate
```

| Model | Fields |
|-------|--------|
| `Candle` | `exchange`, `symbol`, `timeframe`, `timestamp`, `open`, `high`, `low`, `close`, `volume`, `source` |
| `FundingRate` | `exchange`, `symbol`, `timestamp`, `rate`, `predicted_rate`, `next_funding_time`, `source` |

All fields are `str`. Numeric values are parsed and cast at write time.

---

## `crypto_market_data_platform.validation`

```python
from crypto_market_data_platform.validation import (
    validate_candle_batch,
    validate_funding_rate_batch,
    ValidationIssue,
    ValidationResult,
)
```

```python
def validate_candle_batch(candles: list[Candle]) -> ValidationResult:
    """Validates a batch of candles. Returns all issues (non-fail-fast)."""

def validate_funding_rate_batch(rates: list[FundingRate]) -> ValidationResult:
    """Validates a batch of funding rates."""
```

### Data structures

| Class | Fields |
|-------|--------|
| `ValidationIssue` | `severity: str`, `code: str`, `message: str`, `candle_index: int \| None`, `field: str \| None` |
| `ValidationResult` | `passed: bool`, `issues: list[ValidationIssue]` |

### Helper functions

```python
def _decimal_gte(a: str, b: str) -> bool:
    """String-based decimal comparison. Compares integer parts with length-aware
    padding, zero-pads fractional parts. No Decimal objects created."""

def _digit_count(s: str) -> int:
    """Counts significant digits in a decimal string (excludes '.')."""
```

### Regex patterns

```python
_SIGNED_DECIMAL_PATTERN = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
_UNSIGNED_DECIMAL_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)?$")
_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$")
```

See [Validation Rules](validation-rules.md) for the full rule catalogue.

---

## `crypto_market_data_platform.storage`

Low-level write functions. Prefer `OhlcvService` / `FundingRateService`
for normal use.

```python
from crypto_market_data_platform.storage.parquet_writer import (
    candle_to_table,
    funding_rate_to_table,
    write_candles,
    write_funding_rates,
)
```

### Constants

```python
_DECIMAL128_TYPE = pa.decimal128(38, 10)
_ROW_MERGE_THRESHOLD = 50_000
_CANDLE_KEY_COLS = ["exchange", "symbol", "timeframe", "source", "timestamp"]
_FUNDING_RATE_KEY_COLS = ["exchange", "symbol", "source", "timestamp"]
```

### Functions

```python
def candle_to_table(
    candles: list[Candle],
    ts_config: TimestampConfig,
) -> pa.Table:
    """Converts Candle objects to a PyArrow Table with decimal128 and timestamp casts."""

def funding_rate_to_table(
    rates: list[FundingRate],
    ts_config: TimestampConfig,
) -> pa.Table:
    """Converts FundingRate objects to a PyArrow Table."""

def write_candles(
    candles: list[Candle],
    base_path: str = "data",
    ts_config: TimestampConfig | None = None,
    merge_strategy: str = "auto",
) -> list[Path]:
    """Groups candles by partition, merges with existing files, writes Parquet."""

def write_funding_rates(
    rates: list[FundingRate],
    base_path: str = "data",
    ts_config: TimestampConfig | None = None,
    merge_strategy: str = "auto",
) -> list[Path]:
    """Groups funding rates by partition, merges with existing files, writes Parquet."""
```

### Merge functions

```python
def _merge_via_set(
    existing: pa.Table, incoming: pa.Table,
    key_cols: list[str],
) -> pa.Table:
    """In-memory set-based merge. Builds set of existing row keys,
    filters incoming to rows not in existing, concatenates."""

def _merge_via_duckdb(
    existing: pa.Table, incoming: pa.Table,
    key_cols: list[str],
) -> pa.Table:
    """DuckDB ANTI JOIN + UNION ALL merge. Best for large tables."""

def _merge_tables(
    existing: pa.Table, incoming: pa.Table,
    key_cols: list[str],
    strategy: str = "auto",
) -> pa.Table:
    """Dispatches to _merge_via_set or _merge_via_duckdb based on strategy and row count."""
```

### Type cast functions

```python
def _to_decimal128(
    values: list[str], label: str, candle_key: str,
) -> pa.Array:

def _to_timestamp(
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
def _path_for_candle(c: Candle, base_path: str) -> Path: ...
def _path_for_funding_rate(r: FundingRate, base_path: str) -> Path: ...
```

See [Parquet Schema](parquet-schema.md) for the full column type mapping.

---

## `crypto_market_data_platform.ingestion`

High-level ingestion services that combine fetching, validation, and storage.

```python
from crypto_market_data_platform.ingestion import OhlcvService, FundingRateService
```

```python
class OhlcvService:
    def __init__(
        self,
        provider: OHLCVProvider,
        ts_config: TimestampConfig | None = None,
    ) -> None: ...

    def ingest(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        base_path: str = "data",
        merge_strategy: str = "auto",
    ) -> int:
        """Fetch → validate → write. Returns candle count."""


class FundingRateService:
    def __init__(
        self,
        ts_config: TimestampConfig | None = None,
    ) -> None: ...

    def ingest(
        self,
        rates: list[FundingRate],
        base_path: str = "data",
        merge_strategy: str = "auto",
    ) -> int:
        """Validate → write. Returns row count."""
```

---

## `crypto_market_data_platform.query`

```python
from crypto_market_data_platform.query import QueryService, DuckDBQueryService
```

```python
class QueryService(ABC):
    @abstractmethod
    def list_datasets(self, base_path: str = "data") -> dict[str, list[str]]: ...

    @abstractmethod
    def get_candles(
        self,
        base_path: str = "data",
        exchange: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[Candle]: ...

    @abstractmethod
    def get_funding_rates(
        self,
        base_path: str = "data",
        exchange: str | None = None,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        order: str = "DESC",
    ) -> list[FundingRate]: ...

    @abstractmethod
    def get_summary(
        self,
        base_path: str = "data",
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def raw_sql(
        self,
        sql: str,
        base_path: str = "data",
    ) -> list[dict[str, Any]]: ...


class DuckDBQueryService(QueryService):
    """Implementation backed by DuckDB read_parquet."""
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

## `crypto_market_data_platform.config`

```python
from crypto_market_data_platform.config import TimestampConfig
```

```python
@dataclass(slots=True)
class TimestampConfig:
    resolution: str = "s"  # "s" or "us"
    # Computed:
    #   format: str          — "%Y-%m-%dT%H:%M:%S" or "%Y-%m-%dT%H:%M:%S.%f"
    #   parquet_type: pa.DataType  — pa.timestamp("s") or pa.timestamp("us")
```

---

## `crypto_market_data_platform.server`

```python
from crypto_market_data_platform.server import create_app
from crypto_market_data_platform.server.config import ServerConfig
```

```python
def create_app(config: ServerConfig | None = None) -> FastAPI:
    """Factory function. Creates FastAPI app with all routers mounted.
    Injects query_service and base_path into app.state.
    Adds CORSMiddleware (allow all origins/methods/headers).
    Adds global exception handler returning {"error": <msg>, "code": 500}.
    Includes 6 routers: health, datasets, candles, funding, query, summary."""

@dataclass(slots=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    base_path: str = "data"
    query_service: QueryService = field(default_factory=DuckDBQueryService)
```

---

## `crypto_market_data_platform.benchmark`

```python
from crypto_market_data_platform.benchmark import (
    BenchmarkContext, BenchmarkResult, CandlePipelineRunner,
    CrossValidationRule, PipelineRunner, ProviderCandlePipelineRunner,
    RUNNERS, StageMetrics, evaluate_rules,
)
```

```python
class PipelineRunner(ABC):
    @abstractmethod
    def run_coarse(
        self, count: int,
        ts_config: TimestampConfig,
        base_path: str,
    ) -> BenchmarkResult: ...

    def run_verbose(
        self, count: int,
        ts_config: TimestampConfig,
        base_path: str,
    ) -> BenchmarkResult: ...

class CandlePipelineRunner(PipelineRunner):
    """Synthetic benchmark: creates Candle objects → table → write → read."""

class ProviderCandlePipelineRunner(PipelineRunner):
    """Live provider benchmark: fetches real candles → validate → write → read."""
    def __init__(
        self,
        provider: OHLCVProvider,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> None: ...
```

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

## `crypto_market_data_platform.utils`

```python
from crypto_market_data_platform.utils.parquet_viewer import run_inspect
```

```python
def run_inspect(
    path_str: str,
    limit: int = 10,
    start: str | None = None,
    end: str | None = None,
    show_stats: bool = False,
    show_verbose: bool = False,
) -> str:
    """Inspect a Parquet file or directory. Returns formatted text output."""
```
