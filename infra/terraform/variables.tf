variable "subscription_id" {
  description = "Azure subscription ID for the deployment."
  type        = string
}

variable "location" {
  description = "Azure region for all regional resources."
  type        = string
  default     = "East US 2"
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
