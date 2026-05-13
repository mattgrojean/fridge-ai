locals {
  project_name_sanitized = replace(var.project_name, "-", "")

  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }
}
