# ── Application Insights ──────────────────────────────────────────
# Telemetry for the backend Container App. ACA emits trace, request,
# and dependency data automatically when the connection string env
# var is set.

resource "azurerm_application_insights" "cmpd" {
  name                = "${var.prefix}-${var.environment}-ai"
  location            = azurerm_resource_group.cmpd.location
  resource_group_name = azurerm_resource_group.cmpd.name
  workspace_id        = azurerm_log_analytics_workspace.cmpd.id
  application_type    = "web"

  tags = local.tags
}

# ── Action group ──────────────────────────────────────────────────
# Notification target for alerts. Only created when var.alert_email
# is set.

resource "azurerm_monitor_action_group" "cmpd" {
  count = var.alert_email != "" ? 1 : 0

  name                = "${var.prefix}-${var.environment}-ag"
  resource_group_name = azurerm_resource_group.cmpd.name
  short_name          = substr("${var.prefix}ag", 0, 12)

  email_receiver {
    name                    = "admin"
    email_address           = var.alert_email
  }

  tags = local.tags
}

# ── Metric alerts ─────────────────────────────────────────────────

locals {
  action_group_id = var.alert_email != "" ? [azurerm_monitor_action_group.cmpd[0].id] : []
}

resource "azurerm_monitor_metric_alert" "backend_cpu" {
  count = var.alert_email != "" ? 1 : 0

  name                = "${var.prefix}-${var.environment}-backend-cpu"
  resource_group_name = azurerm_resource_group.cmpd.name
  scopes              = [azurerm_container_app.backend.id]
  description         = "Backend CPU usage exceeds 80%"

  criteria {
    metric_namespace = "Microsoft.App/containerapps"
    metric_name      = "CpuUsageReplicas"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = local.action_group_id[0]
  }
}

resource "azurerm_monitor_metric_alert" "backend_memory" {
  count = var.alert_email != "" ? 1 : 0

  name                = "${var.prefix}-${var.environment}-backend-memory"
  resource_group_name = azurerm_resource_group.cmpd.name
  scopes              = [azurerm_container_app.backend.id]
  description         = "Backend memory usage exceeds 80%"

  criteria {
    metric_namespace = "Microsoft.App/containerapps"
    metric_name      = "MemoryUsageReplicas"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = local.action_group_id[0]
  }
}

resource "azurerm_monitor_metric_alert" "backend_replicas" {
  count = var.alert_email != "" ? 1 : 0

  name                = "${var.prefix}-${var.environment}-backend-replicas"
  resource_group_name = azurerm_resource_group.cmpd.name
  scopes              = [azurerm_container_app.backend.id]
  description         = "Backend replicas below minimum"

  criteria {
    metric_namespace = "Microsoft.App/containerapps"
    metric_name      = "ReplicasCount"
    aggregation      = "Minimum"
    operator         = "LessThan"
    threshold        = var.backend_min_replicas
  }

  action {
    action_group_id = local.action_group_id[0]
  }
}

# ── Log alert: HTTP 5xx errors ────────────────────────────────────

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_5xx" {
  count = var.alert_email != "" ? 1 : 0

  name                = "${var.prefix}-${var.environment}-backend-5xx"
  resource_group_name = azurerm_resource_group.cmpd.name
  location            = azurerm_resource_group.cmpd.location
  description         = "Backend returned HTTP 5xx responses"

  evaluation_frequency = "PT5M"
  window_duration      = "PT5M"
  severity             = 1
  target_resource_types = ["Microsoft.App/containerapps"]
  scopes               = [azurerm_container_app.backend.id]

  criteria {
    query                   = <<-EOT
      ContainerAppConsoleLogs_CL
      | where Log_s contains "5xx"
      | summarize Errors = count() by bin(TimeGenerated, 5m)
    EOT
    time_aggregation_method = "Count"
    threshold               = 5
    operator                = "GreaterThan"
    violation {
      fqdn = "ErrorsPerWindow"
    }
  }

  action {
    action_group_id = local.action_group_id[0]
  }
}

# ── Log alert: fetcher job failures ───────────────────────────────

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "fetcher_failures" {
  count = var.alert_email != "" ? 1 : 0

  name                = "${var.prefix}-${var.environment}-fetcher-failures"
  resource_group_name = azurerm_resource_group.cmpd.name
  location            = azurerm_resource_group.cmpd.location
  description         = "Fetcher Container App Job execution failures"

  evaluation_frequency = "PT5M"
  window_duration      = "PT5M"
  severity             = 2
  target_resource_types = ["Microsoft.App/jobs"]
  scopes               = [azurerm_container_app_job.fetcher.id]

  criteria {
    query                   = <<-EOT
      ContainerAppSystemLogs_CL
      | where JobName_s == "fetcher"
      | where Reason_s == "JobExecutionFailed"
      | summarize Failures = count() by bin(TimeGenerated, 5m)
    EOT
    time_aggregation_method = "Count"
    threshold               = 1
    operator                = "GreaterThan"
    violation {
      fqdn = "FailuresPerWindow"
    }
  }

  action {
    action_group_id = local.action_group_id[0]
  }
}
