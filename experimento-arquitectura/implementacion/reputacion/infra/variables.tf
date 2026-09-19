variable "project_id" {
  description = "ID del proyecto de GCP"
  type        = string
}

variable "region" {
  description = "Región de GCP — southamerica-east1 (São Paulo) por defecto, igual que proveedores/infra/variables.tf"
  type        = string
  default     = "southamerica-east1"
}

variable "entorno" {
  description = "Prefijo corto para nombrar todos los recursos de este stack"
  type        = string
  default     = "reputacion-poc"
}

variable "sql_tier" {
  description = "Tier de Cloud SQL — dimensionado para PoC académico, no para producción"
  type        = string
  default     = "db-custom-1-3840"
}
