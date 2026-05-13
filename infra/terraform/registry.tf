resource "azurerm_container_registry" "main" {
  name                = lower("cr${local.project_name_sanitized}${var.environment}")
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
  tags                = local.common_tags
}
