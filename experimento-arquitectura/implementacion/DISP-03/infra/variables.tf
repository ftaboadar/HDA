variable "project_id" {
  description = "ID del proyecto de GCP donde se aprovisiona el experimento DISP-03"
  type        = string
}

variable "region" {
  description = "Región de GCP para los recursos del experimento. southamerica-east1 (São Paulo) es la más cercana a la operación LATAM de HdA; verificar disponibilidad vigente de una región mexicana antes de fijarla (ver .claude/agents/experto-gcp.md)."
  type        = string
  default     = "southamerica-east1"
}

variable "entorno" {
  description = "Prefijo corto para nombrar todos los recursos de este experimento"
  type        = string
  default     = "disp03-poc"
}

variable "sql_tier" {
  description = "Tier de Cloud SQL — dimensionado para PoC académico, no para producción"
  type        = string
  default     = "db-custom-1-3840"
}

variable "max_reintentos" {
  description = "Máximo de reintentos ante falla del sistema externo (ver app/common/config.py)"
  type        = number
  default     = 4
}

variable "timeout_externo_s" {
  description = "Timeout por llamada a un sistema externo, en segundos"
  type        = number
  default     = 3
}
