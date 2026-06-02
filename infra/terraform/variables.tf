variable "subscription_id" {
  description = "Azure subscription ID for the deployment."
  type        = string
}

variable "location" {
  description = "Azure region for all regional resources."
  type        = string
  default     = "Central US"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name used in resource naming."
  type        = string
  default     = "appliance-ai"
}

variable "openai_model_version" {
  description = "Model version for the GPT-4.1-mini deployment."
  type        = string
  default     = "2025-04-14"
}

variable "search_sku" {
  description = "Azure AI Search SKU."
  type        = string
  default     = "basic"
}

variable "foundry_project_name" {
  description = "Name of the Azure AI Foundry project resource."
  type        = string
  default     = "appliance-ai-project"
}
