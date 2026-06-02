resource "azurerm_cognitive_account" "main" {
  name                       = "aify-${var.project_name}-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  kind                       = "AIServices"
  sku_name                   = "S0"
  custom_subdomain_name      = lower("aify-${local.project_name_sanitized}-${var.environment}")
  project_management_enabled = true
  tags                       = local.common_tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_cognitive_account_project" "main" {
  name                 = var.foundry_project_name
  location             = azurerm_resource_group.main.location
  cognitive_account_id = azurerm_cognitive_account.main.id

  identity {
    type = "SystemAssigned"
  }
}
