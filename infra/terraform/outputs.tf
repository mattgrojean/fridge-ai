output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "ai_services_endpoint" {
  value = azurerm_cognitive_account.main.endpoint
}

output "foundry_project_endpoint" {
  value = "https://${azurerm_cognitive_account.main.custom_subdomain_name}.services.ai.azure.com/api/projects/${azurerm_cognitive_account_project.main.name}"
}

output "foundry_project_resource_id" {
  value = azurerm_cognitive_account_project.main.id
}

output "search_endpoint" {
  value = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "search_service_name" {
  value = azurerm_search_service.main.name
}

output "storage_account_name" {
  value = azurerm_storage_account.main.name
}

output "container_registry_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "container_app_url" {
  value = try("https://${azurerm_container_app.main.latest_revision_fqdn}", null)
}

output "entra_client_id" {
  value = azuread_application.main.client_id
}

output "entra_tenant_id" {
  value = data.azuread_client_config.current.tenant_id
}

output "entra_allowed_group_id" {
  value = azuread_group.allowed_users.object_id
}

output "entra_allowed_group_name" {
  value = azuread_group.allowed_users.display_name
}

output "managed_identity_client_id" {
  value = azurerm_user_assigned_identity.main.client_id
}
