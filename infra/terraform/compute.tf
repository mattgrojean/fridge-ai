resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.project_name}-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.common_tags
}

resource "azurerm_container_app" "main" {
  name                         = "ca-${var.project_name}-${var.environment}"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = local.common_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.main.id
  }

  template {
    min_replicas = 0
    max_replicas = 3

    container {
      name   = "chat"
      image  = "${azurerm_container_registry.main.login_server}/appliance-ai-chat:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AZURE_AI_PROJECT_ENDPOINT"
        value = "https://${azurerm_cognitive_account.main.custom_subdomain_name}.services.ai.azure.com/api/projects/${azurerm_cognitive_account_project.main.name}"
      }

      env {
        name  = "FOUNDRY_SEARCH_MCP_ENDPOINT"
        value = "https://${azurerm_search_service.main.name}.search.windows.net/knowledgebases/manuals-kb/mcp?api-version=2025-11-01-preview"
      }

      env {
        name  = "FOUNDRY_AGENT_NAME"
        value = "appliance-repair-agent"
      }

      env {
        name  = "FOUNDRY_KB_CONNECTION_NAME"
        value = "manuals-kb-connection"
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.main.client_id
      }

      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.main.name
      }

      env {
        name  = "AZURE_STORAGE_CONTAINER_NAME"
        value = azurerm_storage_container.manuals.name
      }

      env {
        name  = "SEARCH_INDEX_NAME"
        value = "manuals-index"
      }

      env {
        name  = "ENTRA_CLIENT_ID"
        value = azuread_application.main.client_id
      }

      env {
        name  = "ENTRA_API_SCOPE"
        value = "api://${var.project_name}-${var.environment}/access_as_user"
      }

      env {
        name  = "ENTRA_TENANT_ID"
        value = data.azuread_client_config.current.tenant_id
      }

      env {
        name  = "ENTRA_ALLOWED_GROUP_ID"
        value = azuread_group.allowed_users.object_id
      }

      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.main.connection_string
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  depends_on = [
    azurerm_role_assignment.openai_user,
    azurerm_role_assignment.search_reader,
    azurerm_role_assignment.storage_reader,
    azurerm_role_assignment.storage_delegator,
    azurerm_role_assignment.acr_pull,
    azurerm_role_assignment.project_search_service_contributor,
    azurerm_role_assignment.project_search_index_contributor,
    azurerm_role_assignment.search_cogsvcs_user,
    azurerm_role_assignment.project_foundry_project_manager,
  ]
}
