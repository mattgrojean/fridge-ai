data "azuread_client_config" "current" {}

resource "azurerm_user_assigned_identity" "main" {
  name                = "uami-container-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags
}

resource "azuread_application" "main" {
  display_name            = "Appliance AI Chat (${var.environment})"
  sign_in_audience        = "AzureADMyOrg"
  group_membership_claims = ["SecurityGroup"]
  identifier_uris         = ["api://${var.project_name}-${var.environment}"]

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      admin_consent_description  = "Allow the application to access Appliance AI on behalf of the signed-in user."
      admin_consent_display_name = "Access Appliance AI"
      enabled                    = true
      id                         = "d8c2b8f4-79af-4d6f-8f31-01dbe8b2a8d0"
      type                       = "User"
      user_consent_description   = "Allow the application to access Appliance AI on your behalf."
      user_consent_display_name  = "Access Appliance AI"
      value                      = "access_as_user"
    }
  }

  single_page_application {
    redirect_uris = [
      "https://localhost:8000/",
      "https://ca-${var.project_name}-${var.environment}.${azurerm_container_app_environment.main.default_domain}/"
    ]
  }
}

resource "azuread_service_principal" "main" {
  client_id = azuread_application.main.client_id
}

resource "azuread_group" "allowed_users" {
  display_name            = "Appliance AI Allowed Users (${var.environment})"
  description             = "Users allowed to sign in to Appliance AI (${var.environment})."
  security_enabled        = true
  mail_enabled            = false
  members                 = [data.azuread_client_config.current.object_id]
  owners                  = [data.azuread_client_config.current.object_id]
  prevent_duplicate_names = true
}
