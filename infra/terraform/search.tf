resource "azurerm_search_service" "main" {
  name                         = "srch-${var.project_name}-${var.environment}-01"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = var.location
  sku                          = var.search_sku
  semantic_search_sku          = "standard"
  replica_count                = 1
  partition_count              = 1
  local_authentication_enabled = false
  tags                         = local.common_tags

  identity {
    type = "SystemAssigned"
  }
}
