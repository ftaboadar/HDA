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
    pulsar-infra/gcp (ver ../../DESPLIEGUE-GCP-INTEGRAL.md). Requerida en
    la práctica: el transporte real de Proveedores es Pulsar
    (TRANSPORTE=pulsar en la API, ver cloudrun.tf; el worker arranca sus
    consumidores Pulsar incondicionalmente sin mirar TRANSPORTE — ver
    app/worker/main.py). El default vacío solo evita que `terraform plan`
    falle por falta de valor; con vacío en un apply real, tanto la
    publicación desde la API como los consumidores del worker fallan al
    conectar. Pasar siempre
    `-var "pulsar_service_url=pulsar://<IP_PRIVADA_VM_PULSAR>:6650"` (la
    IP sale de `terraform output -raw ip_privada` en pulsar-infra/gcp).
    Igual que en gestion-de-trabajos/infra, aquí SÍ se habilita Direct
    VPC egress (ver cloudrun.tf, vpc_access en ambos servicios api y
    worker) — sin esa ruta de red el firewall de la VM de Pulsar
    (restringido al rango de la subred del proyecto) rechaza la conexión.
  EOT
  type        = string
  default     = ""
}
