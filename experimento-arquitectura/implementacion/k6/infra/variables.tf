variable "project_id" {
  description = "ID del proyecto de GCP"
  type        = string
}

variable "region" {
  description = "Región de GCP — southamerica-east1 (São Paulo) por defecto, misma región que el resto de los stacks (DISP-03/infra, gestion-de-trabajos/infra, pulsar-infra/gcp) para no meter latencia inter-región en la medición de ESC-01"
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
  default     = "k6-runner-poc"
}

variable "machine_type" {
  description = "e2-standard-4 (4 vCPU, 16GB) — a maxVUs=2000 (esc-01.js), la propia máquina que genera la carga no debe volverse el cuello de botella; sigue siendo tamaño de PoC, no dimensionado para sostener el pico indefinidamente."
  type        = string
  default     = "e2-standard-4"
}

variable "disk_size_gb" {
  description = "Disco de arranque — sobra para el binario de k6 + los JSON de resultados de una corrida de ESC-01"
  type        = number
  default     = 20
}

variable "k6_version" {
  description = "Versión del binario de k6 a instalar (release de GitHub, sin depender de keyserver de apt)"
  type        = string
  default     = "v0.54.0"
}

variable "admin_source_ranges" {
  description = <<-EOT
    Rangos de IP (ej. la IP pública de un desarrollador, "1.2.3.4/32") con
    permiso para conectarse por SSH directo (puerto 22) a esta VM, además
    del túnel IAP que ya está siempre habilitado (ver network.tf). Vacío
    por defecto — sin esto, el único camino de administración es
    `gcloud compute ssh --tunnel-through-iap`.
  EOT
  type        = list(string)
  default     = []
}
