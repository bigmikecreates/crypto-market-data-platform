# API Reference

## CLI

Entry point: `cmpd` (`crypto_market_data_platform.cli.main:app`)

### `cmpd fetch`

Fetch market data and write to partitioned Parquet.

```
cmpd fetch [--mdt {ohlcv,funding-rate}] [--symbol SYMBOL]
           [--timeframe TIMEFRAME] --start START --end END
           [--provider PROVIDER] [--output DIR]
           [--merge-strategy {auto,memory,duckdb}]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--mdt` | `ohlcv` | Market data type (`ohlcv` or `funding-rate`) |
| `--symbol` | `BTC/USDT` | Trading pair symbol |
| `--timeframe` | `1h` | Candle timeframe (ohlcv only) |
| `--start` | required | Start time (ISO-8601: `2026-01-01` or `2026-01-01T00:00:00`) |
| `--end` | required | End time (ISO-8601) |
| `--provider` | `fake` | Data provider (`fake`, `bitfinex`, `bitstamp`, `kucoin`, `bybit`, `mexc`) |
| `--output` | `data` | Base output directory |
| `--merge-strategy` | `auto` | Row merge strategy (`auto`, `memory`, `duckdb`) |

When `--mdt funding-rate`, only `--symbol`, `--start`, `--end`, `--output`,
and `--merge-strategy` apply. The provider is always `FakeProvider`.

---

### `cmpd datasets`

List available datasets grouped by type.

```
cmpd datasets [--path DIR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `data` | Base data directory |

---

### `cmpd inspect`

Inspect a Parquet file or dataset directory.

```
cmpd inspect --path PATH [--limit N] [--start TS] [--end TS]
             [--stats] [--verbose]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | required | Path to a `.parquet` file or dataset directory |
| `--limit`, `-n` | `10` | Max rows in sample |
| `--start` | — | Start of timestamp range (ISO-8601), inclusive |
| `--end` | — | End of timestamp range (ISO-8601), exclusive |
| `--stats` | `False` | Show column statistics |
| `--verbose` | `False` | Show full Parquet metadata |

---

### `cmpd serve`

Start the FastAPI REST server.

```
cmpd serve [--host ADDR] [--port N] [--path DIR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address |
| `--port`, `-p` | `8000` | Bind port |
| `--path` | `data` | Base data directory |

---

### `cmpd query`

Query stored datasets.

#### `cmpd query ohlcv`

```
cmpd query ohlcv [--path DIR] [--exchange EXCH] [--symbol SYM]
                 [--timeframe TF] [--start TS] [--end TS]
                 [--limit N]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `data` | Base data directory |
| `--exchange` | — | Filter by exchange |
| `--symbol` | — | Filter by symbol |
| `--timeframe` | — | Filter by timeframe |
| `--start` | — | Start timestamp (inclusive) |
| `--end` | — | End timestamp (exclusive) |
| `--limit`, `-n` | `10` | Max rows |

#### `cmpd query funding-rate`

```
cmpd query funding-rate [--path DIR] [--exchange EXCH] [--symbol SYM]
                        [--start TS] [--end TS] [--limit N]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `data` | Base data directory |
| `--exchange` | — | Filter by exchange |
| `--symbol` | — | Filter by symbol |
| `--start` | — | Start timestamp (inclusive) |
| `--end` | — | End timestamp (exclusive) |
| `--limit`, `-n` | `10` | Max rows |

#### `cmpd query sql`

```
cmpd query sql "SELECT ..." [--path DIR] [--limit N]
```

| Argument | Description |
|----------|-------------|
| `sql` | SQL query (positional, required) |

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `data` | Base data directory |
| `--limit`, `-n` | `100` | Max rows |

Uses DuckDB `read_parquet` to run the query. Use
`read_parquet('data/**/*.parquet')` to query all stored data.

---

## HTTP API

The REST server is started via `cmpd serve` or directly with:

```python
from crypto_market_data_platform.server import create_app
from crypto_market_data_platform.server.config import ServerConfig

config = ServerConfig(host="0.0.0.0", port=8000, base_path="data")
app = create_app(config)
```

OpenAPI/Swagger UI available at `http://localhost:8000/docs`.

### `GET /health`

Health check.

**Response:** `{"status": "ok"}`

---

### `GET /datasets`

List available datasets grouped by type.

| Query param | Default | Description |
|-------------|---------|-------------|
| `path` | `data` | Base data directory |

**Response:** `dict[str, list[str]]` — e.g. `{"candle": ["bitfinex/BTC/USDT/1h", ...], "funding_rate": [...]}`

---

### `GET /candles`

Query candle data.

| Query param | Default | Description |
|-------------|---------|-------------|
| `path` | `data` | Base data directory |
| `exchange` | — | Filter by exchange |
| `symbol` | — | Filter by symbol |
| `timeframe` | — | Filter by timeframe |
| `start` | — | Start timestamp (inclusive) |
| `end` | — | End timestamp (exclusive) |
| `limit` | `100` | Max rows (1–10 000) |
| `order` | `DESC` | Sort order (`DESC` or `ASC`) |

**Response:** `list[Candle]` (see [Data Model](data-model.md))

---

### `GET /funding-rates`

Query funding rate data.

| Query param | Default | Description |
|-------------|---------|-------------|
| `path` | `data` | Base data directory |
| `exchange` | — | Filter by exchange |
| `symbol` | — | Filter by symbol |
| `start` | — | Start timestamp (inclusive) |
| `end` | — | End timestamp (exclusive) |
| `limit` | `100` | Max rows (1–10 000) |
| `order` | `DESC` | Sort order (`DESC` or `ASC`) |

**Response:** `list[FundingRate]` (see [Data Model](data-model.md))

---

### `GET /summary`

Dataset summary with row counts per partition.

| Query param | Default | Description |
|-------------|---------|-------------|
| `path` | `data` | Base data directory |

**Response:** `list[dict]` with keys `type`, `exchange`, `symbol`, `timeframe`,
`files`, `rows`.

---

### `POST /query`

Run raw SQL via DuckDB `read_parquet`.

**Request body:**

```json
{
  "sql": "SELECT * FROM read_parquet('data/**/*.parquet') LIMIT 5",
  "path": "data"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sql` | `str` | required | SQL query |
| `path` | `str` | `data` | Base data directory |

**Response:** `list[dict]` — each row as a dict with `Decimal` → `str` and
`datetime` → ISO-8601 normalisation.

---

## Python API

### `crypto_market_data_platform.providers`

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

See [Providers](providers.md) for provider-specific details (symbol mappings,
timeframe mappings, rate limits, field order).

---

### `crypto_market_data_platform.models`

```python
from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate
```

| Model | Fields |
|-------|--------|
| `Candle` | `exchange`, `symbol`, `timeframe`, `timestamp`, `open`, `high`, `low`, `close`, `volume`, `source` |
| `FundingRate` | `exchange`, `symbol`, `timestamp`, `rate`, `predicted_rate`, `next_funding_time`, `source` |

All fields are `str`. Numeric values are parsed and cast at write time.
See [Data Model](data-model.md) for rationale.

---

### `crypto_market_data_platform.validation`

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

| Class | Fields |
|-------|--------|
| `ValidationIssue` | `severity: str`, `code: str`, `message: str`, `candle_index: int \| None`, `field: str \| None` |
| `ValidationResult` | `passed: bool`, `issues: list[ValidationIssue]` |

**Validation rules for candles:**

- `EMPTY_FIELD` — no blank required fields
- `INVALID_DECIMAL` — OHLCV values match signed decimal regex
- `NEGATIVE_VALUE` — no negative prices
- `PRECISION_OVERFLOW` — >38 digits (warning)
- `INVALID_TIMESTAMP` — ISO-8601 format
- `OHLC_INVARIANT` — `high >= open`, `high >= close`, `low <= open`, `low <= close`
- `DUPLICATE_TIMESTAMP` — no duplicate keys within batch

**Validation rules for funding rates:**

- `EMPTY_FIELD`, `INVALID_DECIMAL`, `PRECISION_OVERFLOW`
- `FUNDING_RATE_OUT_OF_RANGE` — rate exceeds ±0.5% (warning)
- `INVALID_TIMESTAMP` — checks `timestamp` and `next_funding_time`
- `FUTURE_BEFORE_CURRENT` — `next_funding_time` must be after `timestamp`
- `DUPLICATE_TIMESTAMP` — duplicate key within batch

---

### `crypto_market_data_platform.storage`

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

**Merge strategies** (`merge_strategy`):

| Strategy | Behaviour |
|----------|-----------|
| `auto` | Uses DuckDB merge for batches ≥50 000 rows, in-memory set merge otherwise |
| `memory` | Always use in-memory set-based merge (loads both tables fully) |
| `duckdb` | Always use DuckDB SQL `ANTI JOIN` + `UNION ALL` merge |

**Partition layout:**

```
data/{exchange}/{symbol}/{timeframe}/{date}.parquet        # candles
data/{exchange}/{symbol}/funding_rate/{date}.parquet       # funding rates
```

**Parquet schema (candles):**

| Column | Type |
|--------|------|
| `open` | `decimal128(38, 10)` |
| `high` | `decimal128(38, 10)` |
| `low` | `decimal128(38, 10)` |
| `close` | `decimal128(38, 10)` |
| `volume` | `decimal128(38, 10)` |
| `timestamp` | `timestamp[s]` or `timestamp[us]` |
| `exchange` | `string` (dictionary) |
| `symbol` | `string` (dictionary) |
| `timeframe` | `string` (dictionary) |
| `source` | `string` (dictionary) |

See [Storage E2E](storage-e2e.md) for the full write path.

---

### `crypto_market_data_platform.ingestion`

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

### `crypto_market_data_platform.query`

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
    # Same method signatures as QueryService
```

---

### `crypto_market_data_platform.config`

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

### `crypto_market_data_platform.server`

```python
from crypto_market_data_platform.server import create_app
from crypto_market_data_platform.server.config import ServerConfig
```

```python
def create_app(config: ServerConfig | None = None) -> FastAPI:
    """Factory function. Creates FastAPI app with all routers mounted."""

@dataclass(slots=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    base_path: str = "data"
    query_service: QueryService = field(default_factory=DuckDBQueryService)
```

---

### `crypto_market_data_platform.benchmark`

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

DATACLASSES:
    StageMetrics — name, wall_ms, cpu_ms, mem_delta_mb, peak_mb, gc stats, file_kb
    BenchmarkResult — count, ts_resolution, runner_name, stages, schema, ...
    BenchmarkContext — checkpoint(name, file_kb), total_mem_delta_mb
    CrossValidationRule — name, evaluate(result) -> (rating, message), recommendation
```

`RUNNERS` is a dict mapping `"candle"` → `CandlePipelineRunner` and
`"provider"` → `ProviderCandlePipelineRunner`.

`evaluate_rules(rules, result)` returns `list[(name, rating, message)]`.

See [Benchmark Design](benchmark-design.md) for the full methodology.

---

### `crypto_market_data_platform.utils`

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
