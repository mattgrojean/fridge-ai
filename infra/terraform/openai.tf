resource "azurerm_cognitive_account" "main" {
  name                  = "oai-${var.project_name}-${var.environment}"
  location              = azurerm_resource_group.main.location
  resource_group_name   = azurerm_resource_group.main.name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = lower("oai-${local.project_name_sanitized}-${var.environment}")
  tags                  = local.common_tags
}

resource "azurerm_cognitive_deployment" "chat" {
  name                 = "gpt-4-1-mini"
  cognitive_account_id = azurerm_cognitive_account.main.id

  model {
    format  = "OpenAI"
    name    = "gpt-4.1-mini"
    version = var.openai_model_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = 10
  }
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-3-small"
  cognitive_account_id = azurerm_cognitive_account.main.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }

  sku {
    name     = "Standard"
    capacity = 10
  }
}
