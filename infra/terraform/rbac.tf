resource "azurerm_role_assignment" "openai_user" {
  scope                = azurerm_cognitive_account.main.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "search_reader" {
  scope                = azurerm_search_service.main.id
  role_definition_name = "Search Index Data Reader"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "storage_reader" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "storage_delegator" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Delegator"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "search_blob_reader" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_search_service.main.identity[0].principal_id
}

# Foundry project managed identity → Search (required for Foundry IQ retrieval)
resource "azurerm_role_assignment" "project_search_service_contributor" {
  scope                = azurerm_search_service.main.id
  role_definition_name = "Search Service Contributor"
  principal_id         = azurerm_cognitive_account_project.main.identity[0].principal_id
}

resource "azurerm_role_assignment" "project_search_index_contributor" {
  scope                = azurerm_search_service.main.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azurerm_cognitive_account_project.main.identity[0].principal_id
}

# Search managed identity → AI Services (for LLM-based query planning in Foundry IQ)
resource "azurerm_role_assignment" "search_cogsvcs_user" {
  scope                = azurerm_cognitive_account.main.id
  role_definition_name = "Cognitive Services User"
  principal_id         = azurerm_search_service.main.identity[0].principal_id
}

# Container app managed identity → Foundry project (required to create/invoke hosted agents)
resource "azurerm_role_assignment" "project_foundry_project_manager" {
  scope                = azurerm_cognitive_account_project.main.id
  role_definition_name = "Foundry Project Manager"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}
