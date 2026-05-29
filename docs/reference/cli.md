# CLI Reference

Entry point: `cmpd` (`crypto_market_data_platform.cli.main:app`)

## `cmpd fetch`

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

## `cmpd datasets`

List available datasets grouped by type.

```
cmpd datasets [--path DIR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `data` | Base data directory |

## `cmpd inspect`

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

## `cmpd serve`

Start the FastAPI REST server.

```
cmpd serve [--host ADDR] [--port N] [--path DIR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address |
| `--port`, `-p` | `8000` | Bind port |
| `--path` | `data` | Base data directory |

## `cmpd query`

Query stored datasets.

### `cmpd query ohlcv`

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

### `cmpd query funding-rate`

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

### `cmpd query sql`

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

## Provider registry

```python
PROVIDERS: dict[str, type] = {
    "fake": FakeProvider,
    "bitfinex": BitfinexProvider,
    "bitstamp": BitstampProvider,
    "kucoin": KuCoinProvider,
    "bybit": BybitProvider,
    "mexc": MexcProvider,
}
```
