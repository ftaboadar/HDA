module "api" {
  source = "../../infra-modules/cloud-run-service"

  project_id   = var.project_id
  region       = var.region
  entorno      = var.entorno
  service_name = "api"

  image   = local.imagen_app
  command = ["uvicorn"]
  args    = ["app.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

  enable_cloudsql          = true
  cloudsql_connection_name = google_sql_database_instance.pagos.connection_name

  env_vars = [
    {
      name  = "GCP_PROJECT"
      value = var.project_id
    },
    {
      name  = "LOG_DETALLE"
      value = var.log_detalle
    },
    {
      name      = "DATABASE_URL"
      secret_id = google_secret_manager_secret.db_url.secret_id
    },
    # Sin estas dos, los Adapters de pasarela caen en su default de
    # desarrollo (http://localhost:9100, ver app/common/config.py) y toda
    # llamada a la pasarela falla en Cloud Run. Apuntan a los dos mocks
    # desplegados por el stack mocks-pagos/infra.
    {
      name  = "STRIPE_MOCK_URL"
      value = var.stripe_mock_url
    },
    {
      name  = "MERCADOPAGO_MOCK_URL"
      value = var.mercadopago_mock_url
    },
  ]

  min_instance_count = 0
  max_instance_count = 10

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "runtime_lee_db_url" {
  secret_id = google_secret_manager_secret.db_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.api.service_account_email}"
}
