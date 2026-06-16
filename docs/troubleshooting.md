# Troubleshooting & FAQ

Common issues, their causes, and solutions.

## Connection issues

### "Connection refused" when querying the API

The backend is not running or not reachable.

- **Docker Compose**: Run `docker compose ps` to verify all services are healthy. Check `docker compose logs backend` for errors.
- **Cloud (Azure)**: Verify the backend FQDN resolves and is reachable. Check the Container App logs in the Azure Portal or Application Insights.
- **Port mismatch**: The API runs on port 8050 by default. Verify your `curl` or frontend config matches.

### API key errors (401 Unauthorized)

- The backend requires `X-API-Key` header on all requests except `/health`.
- In the frontend, open **Settings** and enter the same key used by the backend.
- On Docker Compose, the key is set via `CRMD_API_KEY` in `.env`.
- On Azure, the key is stored in Key Vault and passed as an environment variable.

### CORS errors in the frontend

The backend must allow the frontend's origin:

- **Docker Compose**: Set `CRMD_CORS_ORIGINS=http://localhost:3000` in `.env`.
- **Azure**: Set `crmd_cors_origins` in `terraform.tfvars` to the frontend URL.

## Data issues

### No data returned from queries

- The query date range may not overlap stored data. Use `crmd datasets` to see what's available.
- The fetcher may not be running. For Docker Compose, check `docker compose logs fetcher`.
- For cloud deployments, verify the Container App Job ran on schedule.

### Fetcher produces no candles

- The provider may not support the requested symbol/timeframe. Run the fetch with `--provider fake` first to verify the pipeline.
- The date range may be outside the exchange's available history.
- Check the provider's symbol format (see [Providers](providers.md)).

### Duplicate or missing candles

- The writer deduplicates by `(exchange, symbol, timeframe, timestamp)` within each partition. Duplicates within a single fetch are blocked before writing.
- If rows appear with incorrect timestamps, verify the fetch start/end dates and timezone handling.

## Performance

### Slow fetches

- Increase parallelism with `--workers N` to fetch multiple symbols simultaneously.
- Reduce the date range — splits the fetch into smaller chunks.
- Check network latency to the exchange API. The `--timeout` flag controls per-request timeout.

### Slow queries

- Narrow the time range — DuckDB reads fewer Parquet files.
- Avoid querying without filters — full scans of large datasets are slow.
- See [Performance](performance.md) for detailed tuning guidance.

### High memory usage

- Large date ranges load many Parquet rows into memory. Use `--limit` to cap results.
- The DuckDB query service opens a new connection per query — idle connections do not accumulate.

## Deployment

### Docker: permission denied

- The `data` directory must be writable by the container user. Use `chown 1000:1000 /mnt/data` or run the container as root with `user: root`.

### Docker: port already in use

- Change the host port mapping: `ports: "8051:8050"` maps host port 8051 to container port 8050.
- Update the frontend's `NEXT_PUBLIC_API_BASE_URL` to match.

### Azure: Terraform apply fails

- Verify `az account show` returns the correct subscription.
- Some resources (Container App Environment with VNet) require recreation — use `terraform plan` first to see what changes.
- Check Azure quota limits for Container Apps, especially in new subscriptions.

### Azure: Managed identity not authenticating

- Managed identity auto-detection via `DefaultAzureCredential` requires the ACA identity to have `Storage Blob Data Contributor` on the storage account. The Terraform config assigns this role automatically.
- On your local machine, use `az login` or set `AZURE_STORAGE_CONNECTION_STRING`.

## FAQ

### Can I run the frontend separately?

Yes. The frontend is a standard Next.js app. Run `npm run dev` in `frontend/` and set `NEXT_PUBLIC_API_BASE_URL` to point to the backend.

### How do I reset all data?

Stop the services, delete the `data/` directory (or Docker volume), and restart. The fetcher re-fetches from the configured date range.

### Is there a GUI for configuration?

The frontend's [Settings page](/settings) lets you configure the API base URL and API key through the browser. Storage paths, providers, and fetch schedules are configured via environment variables or the CLI.
