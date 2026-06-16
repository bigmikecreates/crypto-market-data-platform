# Upgrading

Instructions for moving between versions of the CrMD Platform.

## Version history

| Version | Date | Notable changes |
|---|---|---|
| 0.1.0 | — | Initial release. |

## How to upgrade

### Local installation

```bash
git pull origin main
pip install -e .
```

If you use extras (Azure, S3, GCS), reinstall with the same extras:

```bash
pip install -e ".[azure,s3,gcs]"
```

### Docker Compose

```bash
docker compose pull
docker compose up -d
```

The backend and fetcher images are tagged with `:latest`. Pin to a specific version in `docker-compose.yml` if needed.

### Azure (Terraform)

```bash
cd infra
terraform init -upgrade
terraform apply
```

Terraform updates the Container App images to the latest `:latest` tag. To pin a version, set the image tag explicitly in `terraform.tfvars`.

## Data format compatibility

Parquet files written by the current version are forward-compatible with future versions. The schema (`exchange`, `symbol`, `timeframe`, `timestamp`, numeric fields as `decimal128(38,10)`) is stable.

If a future version changes the schema:

1. A migration flag or command will be provided.
2. Old Parquet files remain readable — the reader ignores unknown columns.

## Checking the changelog

Release notes are published on the [GitHub releases page](https://github.com/bigmikecreates/crypto-market-data-platform/releases). Subscribe to get notified of new versions.

## See also

- [Self-hosted deployment](deploy/self-hosted.md)
- [Cloud deployment](deploy/cloud.md)
- [Troubleshooting](troubleshooting.md)
