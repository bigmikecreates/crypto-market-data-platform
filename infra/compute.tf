# ── Log Analytics ─────────────────────────────────────────────────
# Required by Container App Environment for monitoring and diagnostics.

resource "azurerm_log_analytics_workspace" "cmpd" {
  name                = "${var.prefix}-${var.environment}-logs"
  location            = azurerm_resource_group.cmpd.location
  resource_group_name = azurerm_resource_group.cmpd.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = local.tags
}

# ── Container App Environment ─────────────────────────────────────

resource "azurerm_container_app_environment" "cmpd" {
  name                       = "${var.prefix}-${var.environment}-ace"
  location                   = azurerm_resource_group.cmpd.location
  resource_group_name        = azurerm_resource_group.cmpd.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.cmpd.id
  infrastructure_subnet_id   = var.use_vnet ? azurerm_subnet.ace[0].id : null

  tags = local.tags
}

# ── Backend container app ─────────────────────────────────────────
# Runs crmd serve — the FastAPI REST server.

resource "azurerm_container_app" "backend" {
  name                         = "${var.prefix}-${var.environment}-backend"
  container_app_environment_id = azurerm_container_app_environment.cmpd.id
  resource_group_name          = azurerm_resource_group.cmpd.name
  revision_mode                = "Single"

  template {
    container {
      name   = "backend"
      image  = "${var.image_name}:${var.image_tag}"
      cpu    = var.backend_cpu
      memory = var.backend_memory

      command = ["crmd", "serve"]
      args = [
        "--host", "0.0.0.0",
        "--path", "az://${azurerm_storage_container.data.name}/data",
      ]

      env {
        name  = "AZURE_STORAGE_ACCOUNT"
        value = azurerm_storage_account.cmpd.name
      }

      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.cmpd.connection_string
      }

      env {
        name  = "CRMD_API_KEY"
        value = var.crmd_api_key
      }

      env {
        name  = "CRMD_CORS_ORIGINS"
        value = var.crmd_cors_origins
      }
    }

    max_replicas = var.backend_max_replicas
    min_replicas = var.backend_min_replicas
  }

  ingress {
    external_enabled = true
    target_port      = 8050
    traffic_weight {
      percentage = 100
      latest_revision = true
    }
  }

  registry {
    server               = var.registry_server
    username             = var.registry_username
    password_secret_name = "registry-password"
  }

  secret {
    name  = "registry-password"
    value = var.registry_password
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.cmpd.id]
  }

  tags = local.tags
}

# ── Fetcher container app job (scheduled) ─────────────────────────
# Runs crmd fetch --since-last on a cron schedule. Each execution
# fetches data since the last stored candle and exits.

resource "azurerm_container_app_job" "fetcher" {
  name                         = "${var.prefix}-${var.environment}-fetcher"
  container_app_environment_id = azurerm_container_app_environment.cmpd.id
  resource_group_name          = azurerm_resource_group.cmpd.name
  location                     = azurerm_resource_group.cmpd.location

  template {
    container {
      name   = "fetcher"
      image  = "${var.image_name}:${var.image_tag}"
      cpu    = var.fetcher_cpu
      memory = var.fetcher_memory

      command = ["crmd", "fetch"]
      args = concat([
        "--mdt", "ohlcv",
        "--output", "az://${azurerm_storage_container.data.name}/data",
        "--since-last",
      ], var.fetcher_extra_args)

      env {
        name  = "AZURE_STORAGE_ACCOUNT"
        value = azurerm_storage_account.cmpd.name
      }

      env {
        name  = "CRMD_API_URL"
        value = "https://${azurerm_container_app.backend.latest_revision_fqdn}"
      }
    }

    max_retry_count = var.fetcher_retries
  }

  schedule_trigger_config {
    cron_expression = var.fetcher_schedule
    parallelism     = 1
  }

  registry {
    server               = var.registry_server
    username             = var.registry_username
    password_secret_name = "registry-password-fetcher"
  }

  secret {
    name  = "registry-password-fetcher"
    value = var.registry_password
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.cmpd.id]
  }

  tags = local.tags
}
