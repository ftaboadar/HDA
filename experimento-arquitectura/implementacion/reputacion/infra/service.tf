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
  cloudsql_connection_name = google_sql_database_instance.reputacion.connection_name

  env_vars = [
    {
      name      = "DATABASE_URL"
      secret_id = google_secret_manager_secret.db_url.secret_id
    },
  ]

  min_instance_count = 0
  max_instance_count = 2

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "runtime_lee_db_url" {
  secret_id = google_secret_manager_secret.db_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.api.service_account_email}"
}

# --------------------------------------------------------------------------
# HALLAZGO EXPLÍCITO — por qué app/infrastructure/messaging/consumidor_pulsar.py
# NO tiene un recurso Cloud Run en este archivo (a diferencia de la API de
# arriba):
#
# Ese consumidor es un loop PULL bloqueante (`while True: consumidor.receive()`,
# ver el propio archivo) SIN ningún servidor HTTP. Cloud Run v2 (services,
# no jobs) exige que el contenedor escuche en `container_port` y responda a
# un probe de arranque/liveness dentro de un plazo acotado -- es el modelo
# "request-driven" descrito en la guía de mapeo GCP del proyecto
# (.claude/agents/experto-gcp.md): "Cloud Run tiene límites de duración de
# request y de conexiones concurrentes -- para workers de larga duración
# consumiendo colas, evaluar GKE o Cloud Run Jobs". Desplegar este
# consumidor tal cual con este módulo fallaría el startup probe (nunca
# abre un puerto), así que NO se intenta aquí -- hacerlo y declarar que
# "queda desplegado" sin haberlo corrido contra GCP real sería falso.
#
# Dos rutas de solución, ninguna implementada en este PR (fuera del
# alcance pedido, que solo cubre Cloud SQL + Cloud Run de la API):
#   1. Agregar un hilo HTTP trivial al propio consumidor (ej. `http.server`
#      respondiendo 200 en el puerto de Cloud Run) + desplegarlo con este
#      mismo módulo, `cpu_idle = false` (CPU siempre asignada -- sin esto
#      Cloud Run puede congelar la CPU del contenedor entre requests HTTP,
#      matando el loop de fondo) y `min_instance_count = max_instance_count = 2`
#      (un solo consumidor; más de una instancia competiría por el mismo
#      backlog de la suscripción sin coordinación adicional). Requiere
#      tocar código de aplicación, que no es el alcance de este stack de
#      infraestructura.
#   2. Desplegarlo en una VM de Compute Engine (mismo patrón que
#      pulsar-infra/gcp/, un `docker run --restart=always` de esta misma
#      imagen con el comando
#      `python -m app.infrastructure.messaging.consumidor_pulsar`) -- cero
#      cambios de código, es la ruta recomendada para este PoC si se
#      necesita el consumidor corriendo de verdad contra GCP.
#
# Referencia cruzada: ver DESPLIEGUE-GCP-INTEGRAL.md, sección "Limitación
# conocida: el consumidor de Pulsar de Reputación".
# --------------------------------------------------------------------------
