# Self-hosted deployment

Run the full `crmd` stack — backend API, data ingestion, and web GUI — on any Linux VM with Docker.

> Prefer managed cloud infrastructure? See [Cloud Deployment](cloud.md) for the Terraform-based Azure deployment.

## Quick start

```bash
# 1. Generate an API key
export CRMD_API_KEY=$(openssl rand -hex 32)

# 2. Create a persistent data directory
mkdir -p /mnt/data

# 3. Start the stack
docker compose up -d

# 4. Verify
curl -H "X-API-Key: $CRMD_API_KEY" http://localhost:8050/datasets
```

This starts three services:

| Service | Port | Role |
|---|---|---|
| `backend` | 8050 | FastAPI server (`crmd serve`) |
| `fetcher` | — | Continuous ingestion (`crmd fetch --since-last --follow`) |
| `frontend` | 3000 | Web console (Next.js) |

## Configuration

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `CRMD_API_KEY` | (required) | API key for backend authentication |
| `CRMD_DATA_DIR` | `/data` | Parquet storage path inside the container |

Set them in a `.env` file next to `docker-compose.yml`:

```bash
echo "CRMD_API_KEY=$(openssl rand -hex 32)" > .env
```

### Persistent volume

Parquet files live in a Docker volume named `data` by default. To use a host directory instead:

```yaml
services:
  backend:
    volumes:
      - /mnt/data:/data
  fetcher:
    volumes:
      - /mnt/data:/data
```

Cloud-specific volume options:

| Cloud | Volume type | Mount point |
|---|---|---|
| AWS | EBS | `/mnt/data` |
| Azure | Managed disk | `/mnt/data` |
| GCP | Persistent disk | `/mnt/data` |
| DigitalOcean | Block storage | `/mnt/data` |

### API key on startup

The `backend` service reads `CRMD_API_KEY` from the environment. If empty the server starts without auth — useful for testing behind a VPN.

## Customising the fetcher

Edit the `fetcher` service command in `docker-compose.yml` to change symbols, providers, or timeframes:

```yaml
services:
  fetcher:
    command: >
      crmd fetch --mdt ohlcv
                 --symbol BTC/USDT --symbol ETH/USDT
                 --timeframe 1h
                 --provider bitfinex
                 --since-last --follow 3600
```

Run `crmd fetch --help` for all options.

## Health checks

The stack includes Docker health checks on all services. The backend exposes `/health` (returns `{"status":"ok"}`); the fetcher waits for the backend to be healthy before starting ingestion. Run `docker compose ps` to see health status.

## Updating

```bash
docker compose pull
docker compose up -d
```

See [Upgrading](../upgrading.md) for version-specific migration notes.

## Manual deployment (without Compose)

```bash
docker run -d \
  --name crmd-server \
  -p 8050:8050 \
  -v /mnt/data:/data \
  -e CRMD_API_KEY="$(openssl rand -hex 32)" \
  --restart unless-stopped \
  ghcr.io/bigmikecreates/crypto-market-data-platform:latest
```
