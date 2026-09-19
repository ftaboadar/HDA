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

  vpc_network = "default"
  # Cloud Run v2 (network_interfaces.subnetwork) exige el formato
  # "projects/*/regions/*/subnetworks/*", no la URL completa de self_link
  # — encontrado corriendo terraform apply real (error 400 de la API),
  # no lo atrapa validate ni plan.
  vpc_subnetwork = data.google_compute_subnetwork.default.id

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
    # Explícitos acá (no solo el default de app/common/config.py) para que
    # los 3 números que deben coincidir -- `max_instance_request_concurrency`
    # (abajo), `DB_POOL_SIZE + DB_MAX_OVERFLOW` (acá) y `max_workers` del
    # ThreadPoolExecutor (app/api/main.py, derivado de estos dos) -- queden
    # visibles juntos en un solo lugar de infra. Ver el comentario junto a
    # `sql_tier` en variables.tf para el cálculo completo de capacidad
    # (por qué 15, no 100 ni 200).
    {
      name  = "DB_POOL_SIZE"
      value = "10"
    },
    {
      name  = "DB_MAX_OVERFLOW"
      value = "5"
    },
    # DISP-02: Throttler hacia el CRM. Sin CRM_MOCK_URL el throttler apunta a
    # su default de desarrollo (localhost:9200) y en Cloud Run toda novedad
    # falla. Los demás valores son los mismos de docker-compose.disp02.yml,
    # ajustados allí por el equipo para drenar una ráfaga 4x sin pérdida.
    {
      name  = "CRM_MOCK_URL"
      value = var.crm_mock_url
    },
    {
      name  = "CRM_LIMITE_RPS"
      value = var.crm_limite_rps
    },
    {
      name  = "THROTTLER_MAX_REINTENTOS"
      value = "6"
    },
    {
      name  = "THROTTLER_BACKOFF_BASE_S"
      value = "0.3"
    },
    {
      name  = "THROTTLER_BACKOFF_MAX_S"
      value = "10"
    },
  ]

  # Antes 0: la corrida de ESC-01 con concurrency=15 mostró "The request
  # was aborted because there was no available instance" en los logs de
  # Cloud Run durante el pico -- el autoscaler se quedó plantado en 10
  # instancias activas (no en el max_instance_count=20 configurado, y no
  # por ninguna cuota de proyecto/región -- se verificó
  # instance_limit_with_direct_vpc_egress_regional=100, muy por encima).
  # Causa real: al bajar concurrency de 200 a 15 para eliminar la
  # sobresuscripción de conexiones, cada instancia aguanta ~13x menos
  # tráfico -- para sostener el mismo pico (1157 req/s) hacen falta muchas
  # más instancias nuevas, arrancando más rápido de lo que un cold start
  # (boot de Python/FastAPI + pool de conexiones) permite. 10 instancias
  # calientes de entrada cubren el nivel que el autoscaler ya demostró
  # necesitar sin cold start; de 10 a 20 (si el pico lo exige) todavía
  # implica arrancar 10 más en caliente -- mitigación parcial, no
  # garantiza cerrar el umbral por sí sola. Costo: instancias facturando
  # de forma continua, no solo bajo demanda -- apagar (min=0) fuera de
  # una corrida de este experimento.
  # min=1 por defecto en hogaralpes (cuota de 20 vCPU/región: 10×2vCPU=20
  # se comía TODA la cuota, sin dejar nada para Proveedores/CRM/Grafana).
  # Para reproducir la corrida real de ESC-01, pasar
  # -var min_instance_count=10 explícitamente (y apagarlo de nuevo después,
  # tal como ya decía este comentario antes de que existiera var.min_instance_count).
  min_instance_count = var.min_instance_count
  max_instance_count = var.max_instance_count
  # Antes 200, desincronizado de max_workers (100 fijo en main.py) y del
  # pool de conexiones (50+50) -- generaba cola interna en la instancia Y
  # sobresuscripción de conexiones contra Cloud SQL al mismo tiempo (dos
  # cuellos de botella apilados, no una sola causa). Ahora == DB_POOL_SIZE +
  # DB_MAX_OVERFLOW (10+5=15) == max_workers del ThreadPoolExecutor -- los
  # 3 deben coincidir siempre. 15 × max_instance_count (20) = 300
  # conexiones en el peor caso, 75% de los 400 `max_connections` por
  # default de Cloud SQL en el tier actual (db-custom-2-7680, 7.5GB según
  # la tabla de Cloud SQL para Postgres) -- ver detalle junto a `sql_tier`.
  max_instance_request_concurrency = 15

  # [2026-09-17] Nunca se había tocado -- Cloud Run asignaba 1 vCPU/512Mi
  # por instancia por default silencioso (infra-modules/cloud-run-service
  # no exponía `cpu`/`memory` antes de hoy). Con containerConcurrency=15 y
  # Python (GIL: un solo hilo ejecuta bytecode a la vez, sin importar
  # cuántos hilos tenga el ThreadPoolExecutor), 15 hilos concurrentes
  # compitiendo por 1 sola vCPU para cualquier trabajo real de CPU
  # (parseo/validación Pydantic, serialización, mapeo de SQLAlchemy) es
  # candidato directo a la variación de latencia sin explicar entre
  # corridas de ESC-01 (ver RESULTADOS-ESCALABILIDAD-GCP.md sección 1.1.1
  # y 3 punto 6) -- nunca se varió esto en toda la sesión de tuning.
  # Subido a 2 vCPU / 1Gi (Cloud Run exige memoria proporcional al pasar
  # de 1 a 2 vCPU) para dar a esos 15 hilos un segundo núcleo real.
  cpu    = "2"
  memory = "1Gi"

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "runtime_lee_db_url" {
  secret_id = google_secret_manager_secret.db_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.api.service_account_email}"
}
