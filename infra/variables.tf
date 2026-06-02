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
