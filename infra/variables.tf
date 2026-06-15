variable "prefix" {
  description = "Short name prefix applied to all resource names (e.g. 'cmpd')."
  type        = string
  default     = "crmd"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,12}[a-z0-9]$", var.prefix))
    error_message = "prefix must be 3-14 lowercase alphanumeric characters or hyphens, starting with a letter."
  }
}

variable "environment" {
  description = "Deployment environment label (dev, staging, prod). Appended to the storage account name."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "eastus"
}

variable "replication_type" {
  description = <<-EOT
    Storage account replication strategy.
    LRS  — locally redundant, cheapest, fine for dev/backfill workloads.
    ZRS  — zone-redundant, recommended for staging.
    GRS  — geo-redundant, recommended for production.
    RAGRS — read-access geo-redundant, highest availability.
  EOT
  type    = string
  default = "LRS"

  validation {
    condition     = contains(["LRS", "ZRS", "GRS", "RAGRS", "GZRS", "RAGZRS"], var.replication_type)
    error_message = "replication_type must be one of: LRS, ZRS, GRS, RAGRS, GZRS, RAGZRS."
  }
}

variable "container_name" {
  description = "Blob container name. Used as the top-level path in az:// URIs."
  type        = string
  default     = "market-data"
}

variable "key_vault_sku" {
  description = "SKU for the Key Vault (standard or premium)."
  type        = string
  default     = "standard"

  validation {
    condition     = contains(["standard", "premium"], var.key_vault_sku)
    error_message = "key_vault_sku must be 'standard' or 'premium'."
  }
}

# ── Container image ───────────────────────────────────────────────

variable "image_name" {
  description = "Container image name (without tag)."
  type        = string
  default     = "ghcr.io/bigmikecreates/crypto-market-data-platform"
}

variable "image_tag" {
  description = "Container image tag."
  type        = string
  default     = "latest"
}

variable "registry_server" {
  description = "Container registry server (e.g. ghcr.io)."
  type        = string
  default     = "ghcr.io"
}

variable "registry_username" {
  description = "Container registry username for image pulls."
  type        = string
  default     = ""
}

variable "registry_password" {
  description = "Container registry password/token for image pulls."
  type        = string
  sensitive   = true
  default     = ""
}

# ── Backend (Container App) ───────────────────────────────────────

variable "backend_cpu" {
  description = "CPU cores for the backend container app."
  type        = string
  default     = "0.5"
}

variable "backend_memory" {
  description = "Memory for the backend container app (e.g. '1.0Gi')."
  type        = string
  default     = "1.0Gi"
}

variable "backend_min_replicas" {
  description = "Minimum number of backend replicas."
  type        = number
  default     = 1
}

variable "backend_max_replicas" {
  description = "Maximum number of backend replicas (scale-to-zero not used when min_replicas >= 1)."
  type        = number
  default     = 3
}

variable "crmd_api_key" {
  description = "API key for the FastAPI server. Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
  type        = string
  sensitive   = true
  default     = ""
}

variable "crmd_cors_origins" {
  description = "Comma-separated CORS origins for the FastAPI server."
  type        = string
  default     = "http://localhost:3000,http://127.0.0.1:3000"
}

# ── Fetcher (Container App Job) ───────────────────────────────────

variable "fetcher_cpu" {
  description = "CPU cores for the fetcher job."
  type        = string
  default     = "0.25"
}

variable "fetcher_memory" {
  description = "Memory for the fetcher job."
  type        = string
  default     = "0.5Gi"
}

variable "fetcher_schedule" {
  description = "Cron expression for the fetcher job schedule."
  type        = string
  default     = "0 */6 * * *"
}

variable "fetcher_retries" {
  description = "Maximum retry count for failed fetcher executions."
  type        = number
  default     = 3
}

variable "fetcher_extra_args" {
  description = "Additional CLI args passed to crmd fetch (symbol, timeframe, provider, etc.)."
  type        = list(string)
  default     = ["--symbol", "BTC/USDT", "--timeframe", "1h", "--provider", "bitfinex"]
}
