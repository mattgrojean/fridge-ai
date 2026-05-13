data "azuread_client_config" "current" {}

resource "azurerm_user_assigned_identity" "main" {
  name                = "id-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags
}

resource "azuread_application" "main" {
  display_name     = "Appliance AI Chat (${var.environment})"
  sign_in_audience = "AzureADMyOrg"

  single_page_application {
    # Replace the placeholder URI with the Container App URL after the first deployment.
    redirect_uris = [
      "https://localhost:8000/",
      "https://placeholder.azurecontainerapps.io/"
    ]
  }
}

resource "azuread_service_principal" "main" {
  client_id = azuread_application.main.client_id
}
