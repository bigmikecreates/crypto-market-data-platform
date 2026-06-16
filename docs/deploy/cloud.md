# Cloud deployment (Azure)

Deploy the full `crmd` stack to Azure Container Apps using Terraform. This provisions a managed, autoscaling backend API, a scheduled fetcher job, and monitoring infrastructure — suitable for production and team use.

## Quick start

```bash
# 1. Login to Azure
az login

# 2. Create a tfvars file
cat > terraform.tfvars <<EOF
prefix         = "crmd"
environment    = "prod"
location       = "eastus"
crmd_api_key   = "$(openssl rand -hex 32)"
alert_email    = "team@example.com"
EOF

# 3. Deploy
cd infra
terraform init
terraform apply -auto-approve
```

The deployment creates:

| Resource | Purpose |
|---|---|
| Container App Environment | Managed Kubernetes with Log Analytics |
| Backend Container App | FastAPI server (`crmd serve`) on port 8050 |
| Fetcher Container App Job | Scheduled cron ingestion (`crmd fetch --since-last`) |
| Azure Blob Storage | Parquet data lake |
| Key Vault | Secrets: storage connection string, API key, registry password |
| Application Insights | Request tracing, dependency monitoring |
| Action group + alerts | CPU, memory, HTTP 5xx, fetcher failure notifications |

## Accessing the backend

After deployment, Terraform outputs the backend FQDN:

```bash
terraform output backend_fqdn
```

Verify the deployment:

```bash
curl -H "X-API-Key: $(terraform output -raw crmd_api_key)" \
  https://<backend-fqdn>/health
```

## Configuration

### Required variables

| Variable | Description |
|---|---|
| `prefix` | Resource name prefix (lowercase, 3-8 chars) |
| `environment` | Environment name (`dev`, `staging`, `prod`) |
| `location` | Azure region (e.g. `eastus`, `westeurope`) |
| `crmd_api_key` | API key for backend authentication |

### Optional variables

| Variable | Default | Description |
|---|---|---|
| `crmd_cors_origins` | `http://localhost:3000` | Comma-separated CORS origins |
| `use_vnet` | `false` | Deploy into a dedicated VNet (requires recreation) |
| `dns_domain` | `""` | Custom domain for a public DNS zone + CNAME |
| `alert_email` | `""` | Email address for monitoring alerts |
| `min_replicas` | `1` | Minimum backend replicas |
| `max_replicas` | `10` | Maximum backend replicas (scale threshold) |

### VNet integration

Set `use_vnet = true` to deploy the Container App Environment into a dedicated subnet with an NSG. This is required for private network access but forces recreation of the ACE — toggle before production data is stored.

### Custom domain

Set `dns_domain = "api.example.com"` to create a public DNS zone and CNAME record pointing to the backend FQDN.

## Monitoring alerts

When `alert_email` is set, the deployment creates:

| Alert | Condition |
|---|---|
| CPU >80% | Average CPU across replicas |
| Memory >80% | Average memory across replicas |
| Replica count | Replicas below minimum |
| HTTP 5xx errors | Any 5xx response from the backend |
| Fetcher job failure | Scheduled cron job exits with error |

## Authentication

The backend uses `AZURE_STORAGE_ACCOUNT` with `DefaultAzureCredential` (automatic managed identity detection in ACA). No connection string is needed when deploying via Terraform — the managed identity on the Container App has `Storage Blob Data Contributor` access to the storage account.

## Cleanup

```bash
terraform destroy
```

This removes all Azure resources. Data in the storage account is deleted unless you add `prevent_destroy` to the storage account resource.

## See also

- [Self-hosted deployment](self-hosted.md) — Docker Compose on a single VM
- [Architecture](../architecture.md) — pipeline design overview
- [Troubleshooting](../troubleshooting.md) — common Azure deployment issues
