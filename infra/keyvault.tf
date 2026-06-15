# ── Key Vault ─────────────────────────────────────────────────────
# Stores secrets for Container Apps. Uses RBAC so the managed
# identity reads secrets without managing access policies.

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "cmpd" {
  name                       = "${var.prefix}${var.environment}kv"
  location                   = azurerm_resource_group.cmpd.location
  resource_group_name        = azurerm_resource_group.cmpd.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = var.key_vault_sku
  enable_rbac_authorization  = true
  purge_protection_enabled   = false
  soft_delete_retention_days = 7

  tags = local.tags
}

# ── Secrets ───────────────────────────────────────────────────────

resource "azurerm_key_vault_secret" "storage_connection_string" {
  name         = "storage-connection-string"
  value        = azurerm_storage_account.cmpd.primary_connection_string
  key_vault_id = azurerm_key_vault.cmpd.id
}

resource "azurerm_key_vault_secret" "crmd_api_key" {
  name         = "crmd-api-key"
  value        = var.crmd_api_key
  key_vault_id = azurerm_key_vault.cmpd.id
}

resource "azurerm_key_vault_secret" "registry_password" {
  name         = "registry-password"
  value        = var.registry_password
  key_vault_id = azurerm_key_vault.cmpd.id
}

# ── RBAC: managed identity can read secrets ───────────────────────

resource "azurerm_role_assignment" "key_vault_secrets_user" {
  scope                = azurerm_key_vault.cmpd.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.cmpd.principal_id
}
