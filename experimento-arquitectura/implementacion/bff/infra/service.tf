module "api" {
  source = "../../infra-modules/cloud-run-service"

  project_id   = var.project_id
  region       = var.region
  entorno      = var.entorno
  service_name = "api"

  image   = local.imagen_app
  command = ["uvicorn"]
  args    = ["app.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

  enable_cloudsql    = false
  min_instance_count = 0
  max_instance_count = 2

  env_vars = [
    { name = "GESTION_TRABAJOS_URL", value = var.gestion_trabajos_url },
    { name = "PROVEEDORES_URL", value = var.proveedores_url },
    { name = "PAGOS_URL", value = var.pagos_url },
    { name = "SINIESTROS_URL", value = var.siniestros_url },
    { name = "MARKETPLACE_URL", value = var.marketplace_url },
    { name = "SUSCRIPCIONES_URL", value = var.suscripciones_url },
    { name = "SCORING_URL", value = var.scoring_url },
    { name = "REPUTACION_URL", value = var.reputacion_url },
  ]

  depends_on = [google_project_service.apis]
}
