# Performance tuning

Guidelines for optimising ingestion throughput and query response times.

## Ingestion

### Parallel fetch

The CLI `--workers` flag controls concurrent symbol fetching. Each worker fetches one symbol at a time in a separate thread:

```bash
crmd fetch \
  --symbol "BTC/USDT" --symbol "ETH/USDT" --symbol "SOL/USDT" \
  --timeframe 1h \
  --start 2026-01-01 --end 2026-01-08 \
  --provider bitfinex \
  --workers 3
```

Choose the worker count based on:

- **Exchange rate limits** — start with `2-4` workers for most exchanges; increase if the API does not rate-limit
- **Network latency** — higher latency benefits from more workers (pipelining)
- **CPU cores** — avoid exceeding available cores; each worker does JSON parsing + validation

### Time range chunking

The fetcher splits the requested time range into daily chunks. Each chunk produces a single Parquet partition. This is automatic — no configuration needed.

To reduce API pressure per symbol, use shorter ranges:

```bash
# One week per invocation
crmd fetch --symbol "BTC/USDT" --start 2026-01-01 --end 2026-01-08
```

### Storage I/O

- **Local disk**: Use SSDs for Parquet storage. HDDs bottleneck merge operations on large partitions.
- **Azure Blob**: Transfer speed depends on the Blob Storage tier. Standard tier is sufficient for moderate throughput; Premium tier improves concurrent access.
- **S3/GCS**: Network latency dominates. Use `--workers` to pipeline requests.

## Query performance

### Time range filtering

Always include `--start` and `--end` when querying. DuckDB can skip partitions outside the range, reducing I/O:

```bash
# Fast — reads one partition
crmd query ohlcv --symbol "BTC/USDT" --start 2026-01-01 --end 2026-01-02

# Slow — scans all partitions
crmd query ohlcv --symbol "BTC/USDT"
```

### Limit results

Use `--limit` to cap the number of returned rows when you only need a sample:

```bash
crmd query ohlcv --symbol "BTC/USDT" --limit 100
```

### Query service configuration

The query service creates a new DuckDB in-memory connection per request. Key settings:

| Setting | Default | Tuning |
|---|---|---|
| `memory_limit` | 4 GB | Increase for large aggregations |
| `threads` | CPU count | Reduce to limit concurrency |
| `enable_progress_bar` | off | Disable for non-interactive use |

Set these via `crmd serve` with DuckDB configuration:

```bash
crmd serve \
  --path data/ \
  --port 8050 \
  --duckdb-memory-limit 8GB \
  --duckdb-threads 4
```

### Column pruning

Parquet is a columnar format. Queries that only read a subset of columns are faster:

```
# SELECT timestamp, close — reads only 2 columns
# vs SELECT * — reads all 9 columns
```

The CLI and API always request all columns. Custom applications using DuckDB directly can prune.

## Resource limits

### Docker Compose

Resource limits in `docker-compose.yml` prevent the stack from starving the host:

| Service | Memory | CPU |
|---|---|---|
| `backend` | 512 MB | 1.0 |
| `fetcher` | 256 MB | 0.5 |
| `frontend` | 512 MB | 1.0 |

Adjust these based on your workload — large parallel fetches benefit from more CPU.

### Cloud (Azure)

Terraform configures autoscaling for the backend Container App:

```hcl
min_replicas = 1
max_replicas = 10
```

Scales based on HTTP traffic and CPU/memory metrics. The fetcher is a scheduled job — it runs, ingests, and exits, so it incurs no ongoing cost.

## Benchmarking

For systematic performance measurement, see [Benchmark Design](benchmark-design.md). The pipeline includes two measurement modes:

- **Default** — realistic performance under normal load
- **`--isolated`** — dedicated core, high priority, revealing inherent cost

## See also

- [Benchmark Design](benchmark-design.md) — methodology and interpretation
- [Design Rationale](benchmarks/design-rationale.md) — data-driven decisions
- [Troubleshooting](troubleshooting.md) — common performance issues
