terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
  }

  # Local backend is the default for first-time setup.
  # To migrate state to Azure Storage (recommended for teams), replace this block with:
  #
  # backend "azurerm" {
  #   resource_group_name  = "cmpd-tfstate-rg"
  #   storage_account_name = "cmpdtfstate"   # must be globally unique
  #   container_name       = "tfstate"
  #   key                  = "cmpd.tfstate"
  # }
  #
  # Bootstrap the backend once with:
  #   az group create -n cmpd-tfstate-rg -l eastus
  #   az storage account create -n cmpdtfstate -g cmpd-tfstate-rg --sku Standard_LRS
  #   az storage container create -n tfstate --account-name cmpdtfstate
  #   terraform init -migrate-state
}

provider "azurerm" {
  features {}
}

# ── Resource group ────────────────────────────────────────────────────────────

resource "azurerm_resource_group" "cmpd" {
  name     = "${var.prefix}-rg"
  location = var.location

  tags = local.tags
}

# ── Storage account + container ───────────────────────────────────────────────

resource "azurerm_storage_account" "cmpd" {
  # Storage account names must be globally unique, 3-24 chars, lowercase alphanumeric.
  name                = "${replace(var.prefix, "-", "")}${var.environment}sa"
  resource_group_name = azurerm_resource_group.cmpd.name
  location            = azurerm_resource_group.cmpd.location

  account_tier             = "Standard"
  account_replication_type = var.replication_type
  min_tls_version          = "TLS1_2"

  blob_properties {
    # Soft-delete gives a 7-day recovery window — cheap safety net.
    delete_retention_policy {
      days = 7
    }
  }

  tags = local.tags
}

resource "azurerm_storage_container" "data" {
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.cmpd.id
  container_access_type = "private"
}

# ── Managed identity for production (no long-lived keys in env vars) ──────────

resource "azurerm_user_assigned_identity" "cmpd" {
  name                = "${var.prefix}-identity"
  resource_group_name = azurerm_resource_group.cmpd.name
  location            = azurerm_resource_group.cmpd.location

  tags = local.tags
}

# Storage Blob Data Contributor lets the identity read, write, and delete blobs.
# Scope is the storage account so the identity works across all containers.
resource "azurerm_role_assignment" "blob_contributor" {
  scope                = azurerm_storage_account.cmpd.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.cmpd.principal_id
}

# ── Locals ────────────────────────────────────────────────────────────────────

locals {
  tags = {
    project     = "crypto-market-data-platform"
    environment = var.environment
    managed-by  = "terraform"
  }
}
