output "resource_group_name" {
  description = "Name of the provisioned resource group."
  value       = azurerm_resource_group.cmpd.name
}

output "storage_account_name" {
  description = "Storage account name (needed for AZURE_STORAGE_ACCOUNT env var)."
  value       = azurerm_storage_account.cmpd.name
}

output "container_name" {
  description = "Blob container name."
  value       = azurerm_storage_container.data.name
}

output "data_root_uri" {
  description = <<-EOT
    Pass this value as --output / --path to cmpd.
    Example: cmpd fetch ... --output $(terraform output -raw data_root_uri)
  EOT
  value = "az://${azurerm_storage_container.data.name}/data"
}

output "connection_string" {
  description = <<-EOT
    Primary connection string for AZURE_STORAGE_CONNECTION_STRING.
    Retrieve with: terraform output -raw connection_string
    Do NOT commit this value to version control.
  EOT
  value     = azurerm_storage_account.cmpd.primary_connection_string
  sensitive = true
}

output "managed_identity_client_id" {
  description = <<-EOT
    Client ID of the user-assigned managed identity.
    Assign this identity to your compute resource (ACI, ACA, AVM) and set
    AZURE_STORAGE_ACCOUNT + AZURE_CLIENT_ID instead of a connection string.
  EOT
  value = azurerm_user_assigned_identity.cmpd.client_id
}

output "managed_identity_id" {
  description = "Full resource ID of the managed identity, for assignment to compute resources."
  value       = azurerm_user_assigned_identity.cmpd.id
}

output "backend_url" {
  description = "HTTPS URL of the backend Container App."
  value       = "https://${azurerm_container_app.backend.latest_revision_fqdn}"
}

output "container_app_environment_id" {
  description = "Resource ID of the Container App Environment."
  value       = azurerm_container_app_environment.cmpd.id
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.cmpd.id
}

output "fetcher_job_name" {
  description = "Name of the fetcher Container App Job (for az CLI monitoring)."
  value       = azurerm_container_app_job.fetcher.name
}
