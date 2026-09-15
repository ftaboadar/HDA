# Direct VPC egress: SOLO así el tráfico saliente de este servicio hacia
# la VM de Pulsar (pulsar-infra/gcp) sale realmente por la subred
# "default" de la VPC del proyecto -- sin esto, el firewall de esa VM
# (restringido al rango de la subred, no 0.0.0.0/0) rechazaría la
# conexión, porque el egress serverless por defecto de Cloud Run se
# origina desde IPs de Google, no de la VPC del cliente. Ver
# infra-modules/cloud-run-service/variables.tf (vpc_network) y
# ../../DESPLIEGUE-GCP-INTEGRAL.md para la justificación completa.
#
# egress = PRIVATE_RANGES_ONLY (default del módulo): solo el tráfico con
# destino RFC1918 (la IP interna de la VM de Pulsar) se enruta por la
# VPC -- las llamadas de este servicio a los mocks de pagos (Cloud Run
# público) siguen su camino normal de internet, sin costo ni latencia
# extra de por medio.
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
  cloudsql_connection_name = google_sql_database_instance.gestion_trabajos.connection_name

  vpc_network    = "default"
  # Cloud Run v2 (network_interfaces.subnetwork) exige el formato
  # "projects/*/regions/*/subnetworks/*", no la URL completa de self_link
  # — encontrado corriendo terraform apply real (error 400 de la API),
  # no lo atrapa validate ni plan.
  vpc_subnetwork = data.google_compute_subnetwork.default.id

  env_vars = [
    {
      name      = "DATABASE_URL"
      secret_id = google_secret_manager_secret.db_url.secret_id
    },
    {
      name  = "PULSAR_SERVICE_URL"
      value = var.pulsar_service_url
    },
    {
      name  = "PULSAR_TOPIC_TRABAJOS_FINALIZADO"
      value = var.pulsar_topic_trabajos_finalizado
    },
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
