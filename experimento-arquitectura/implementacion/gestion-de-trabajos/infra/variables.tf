variable "project_id" {
  description = "ID del proyecto de GCP"
  type        = string
}

variable "region" {
  description = "Región de GCP — southamerica-east1 (São Paulo) por defecto, igual que DISP-03/infra/variables.tf"
  type        = string
  default     = "southamerica-east1"
}

variable "entorno" {
  description = "Prefijo corto para nombrar todos los recursos de este stack"
  type        = string
  default     = "gestion-trabajos-poc"
}

variable "sql_tier" {
  description = "Tier de Cloud SQL — dimensionado para PoC académico, no para producción"
  type        = string
  default     = "db-custom-1-3840"
}

variable "pulsar_service_url" {
  description = <<-EOT
    URL del broker de Pulsar (pulsar://host:6650). Viene del output
    "ip_privada" del stack pulsar-infra/gcp (NO "ip_publica" — este
    servicio alcanza la VM por su IP interna vía Direct VPC egress, ver
    service.tf; la IP pública de la VM es solo para
    administración/debug manual desde fuera de la VPC). Ver
    ../../DESPLIEGUE-GCP-INTEGRAL.md para el orden de apply.
  EOT
  type        = string
  default     = "pulsar://localhost:6650"
}

variable "pulsar_topic_trabajos_finalizado" {
  type    = string
  default = "persistent://hda/gestion-trabajos/trabajos.finalizado"
}

variable "stripe_mock_url" {
  description = "Output \"uri\" del servicio mock-stripe del stack mocks-pagos/infra"
  type        = string
  default     = "http://localhost:9100"
}

variable "mercadopago_mock_url" {
  description = "Output \"uri\" del servicio mock-mercadopago del stack mocks-pagos/infra"
  type        = string
  default     = "http://localhost:9100"
}
