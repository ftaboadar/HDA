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
  default     = "bff-poc"
}

variable "sql_tier" {
  description = "Tier de Cloud SQL — dimensionado para PoC académico, no para producción"
  type        = string
  default     = "db-custom-1-3840"
}

# URLs de Cloud Run de los servicios downstream (salida `api_url` de cada stack).
# El BFF es el último stack que aplica desplegar-todo.sh precisamente para poder
# pasar estas URLs ya conocidas — ver bff/app/api/main.py SERVICE_URLS.
variable "gestion_trabajos_url" {
  type = string
}
variable "proveedores_url" {
  type = string
}
variable "pagos_url" {
  type = string
}
variable "siniestros_url" {
  type = string
}
variable "marketplace_url" {
  type = string
}
variable "suscripciones_url" {
  type = string
}
variable "scoring_url" {
  type = string
}
variable "reputacion_url" {
  type = string
}
