resource "azurerm_storage_account" "main" {
  name                            = lower(substr("st${local.project_name_sanitized}${var.environment}", 0, 24))
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  allow_nested_items_to_be_public = false
  tags                            = local.common_tags
}

resource "azurerm_storage_container" "manuals" {
  name                  = "manuals"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "conversations" {
  name                  = "conversations"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}
