variable "project_id" {
  description = "ID del proyecto de GCP"
  type        = string
}

variable "region" {
  description = "Región de GCP — southamerica-east1 (São Paulo) por defecto, igual que proveedores/infra/variables.tf"
  type        = string
  default     = "southamerica-east1"
}

variable "zone" {
  description = "Zona de la VM — por defecto la zona \"a\" de var.region"
  type        = string
  default     = null
}

variable "entorno" {
  description = "Prefijo corto para nombrar todos los recursos de este stack"
  type        = string
  default     = "pulsar-poc"
}

variable "machine_type" {
  description = "e2-standard-4 (4 vCPU, 16GB) — Zookeeper+BookKeeper+Broker en la misma VM necesitan más que un e2-medium; sigue siendo un tamaño de PoC, no el dimensionado de ../helm/values.yaml para un cluster multi-réplica real."
  type        = string
  default     = "e2-standard-4"
}

variable "disk_size_gb" {
  description = "Disco de arranque — incluye los volúmenes Docker de zk-data/bk-data del propio docker-compose.yml, que viven dentro del filesystem de la VM"
  type        = number
  default     = 60
}

variable "admin_source_ranges" {
  description = <<-EOT
    Rangos de IP adicionales (ej. la IP pública de un desarrollador,
    "1.2.3.4/32") con permiso para llegar al puerto 8080 (admin REST de
    Pulsar) desde fuera de la VPC del proyecto, para depuración manual
    con curl/pulsar-admin. Vacío por defecto — sin esto, 8080 solo es
    alcanzable desde dentro de la VPC (ver network.tf), igual que 6650.
  EOT
  type        = list(string)
  default     = []
}
