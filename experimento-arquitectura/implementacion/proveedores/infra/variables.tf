variable "project_id" {
  description = "ID del proyecto de GCP donde se aprovisiona el servicio Proveedores (escenario DISP-03)"
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

variable "pulsar_service_url" {
  description = <<-EOT
    URL del broker de Apache Pulsar (pulsar://host:6650), del stack
    pulsar-infra/gcp (ver ../../DESPLIEGUE-GCP-INTEGRAL.md). Default
    vacío: el transporte real de Proveedores sigue siendo Pub/Sub
    (TRANSPORTE=pubsub, ver pubsub.tf) — esta variable NO cambia ese
    comportamiento, solo deja la env var disponible por si algún día
    DISP-03 migra de transporte (igual que ya existe
    PUBSUB_TOPIC_EVENTOS sin que la API lo use todavía). A diferencia de
    gestion-de-trabajos/infra, aquí NO se habilita Direct VPC egress para
    esto: como ningún código de app/ la lee hoy, no hay nada real que
    conectar, y agregar esa complejidad de red sin uso sería prematuro.
  EOT
  type        = string
  default     = ""
}
