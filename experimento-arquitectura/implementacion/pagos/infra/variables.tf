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
  default     = "pagos-poc"
}

variable "sql_tier" {
  description = "Tier de Cloud SQL — dimensionado para PoC académico, no para producción"
  type        = string
  default     = "db-custom-1-3840"
}

variable "stripe_mock_url" {
  description = "Output \"mock_stripe_url\" del stack mocks-pagos/infra — lo consume el Adapter PasarelaStripe (MOD-02)"
  type        = string
  default     = "http://localhost:9100"
}

variable "mercadopago_mock_url" {
  description = "Output \"mock_mercadopago_url\" del stack mocks-pagos/infra — lo consume el Adapter PasarelaMercadoPago (MOD-02)"
  type        = string
  default     = "http://localhost:9100"
}

variable "log_detalle" {
  description = "\"completo\" (default) emite los logs de trazado fino por request (http_request_completada, comando_*, mensaje_publicado...). \"minimo\" los apaga: usarlo en una corrida real de ESC-01, donde un log extra por request cuesta CPU y dinero en Cloud Logging."
  type        = string
  default     = "completo"
}
