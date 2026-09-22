# Grafana real (imagen pública oficial de Docker Hub, sin pasar por
# Artifact Registry — Cloud Run v2 soporta imágenes públicas directas) con
# persistencia MÍNIMA: sin Cloud SQL ni disco propio para la base SQLite
# interna de Grafana (usuarios, alertas, cambios manuales de UI) — eso se
# pierde en cada scale-to-zero/cold start o nueva revisión. Lo que SÍ
# persiste entre reinicios son el datasource y el dashboard de ejemplo,
# provisionados como archivos vía un volumen GCS FUSE de solo lectura
# (Cloud Run v2 soporta volúmenes `gcs` nativos, ver
# infra-modules/cloud-run-service — este servicio no usa ese módulo
# porque necesita ese volumen GCS y variables de entorno muy específicas
# de Grafana que no vale la pena generalizar en un módulo pensado para
# los 3 microservicios propios).
#
# Limitación documentada explícitamente (tal como pide la tarea): un
# reinicio de Grafana (cold start tras scale-to-zero, o un nuevo deploy)
# vuelve a arrancar con una base SQLite vacía — cualquier dashboard creado
# a mano desde la UI, o cualquier usuario/alerta configurado manualmente,
# desaparece. El dashboard de ejemplo (dashboard.json) y el datasource de
# Cloud Monitoring SÍ sobreviven porque se recargan del volumen
# provisionado en cada arranque. Para persistencia real de la base de
# Grafana (multiusuario, alerting propio, etc.) el camino sería Cloud SQL
# (Grafana soporta Postgres/MySQL como backend de su propia base vía
# GF_DATABASE_*) — deliberadamente fuera de alcance de este PoC (más
# costo, más complejidad, y la tarea pide explícitamente aceptar esta
# limitación en vez de resolverla).

resource "google_service_account" "grafana" {
  account_id   = "${var.entorno}-grafana"
  display_name = "Runtime de Grafana (${var.entorno})"
}

# Necesario para que el datasource "Google Cloud Monitoring"
# (jsonData.authenticationType = gce, ver templates/datasource.yaml)
# pueda consultar métricas reales de los 3 microservicios + Proveedores.
resource "google_project_iam_member" "grafana_monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.grafana.email}"
}

# roles/monitoring.viewer NO incluye acceso a Cloud Logging — es un permiso
# aparte. Sin esto, el datasource "Google Cloud Logging" se provisiona pero
# falla con 403 en la primera consulta.
resource "google_project_iam_member" "grafana_logging_viewer" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.grafana.email}"
}

# Los nombres de bucket de GCS son globales y cada componente separado por
# "." está limitado a 63 caracteres (sin dominio aquí, así que el nombre
# completo cae bajo ese límite). Un `project_id` auto-generado por GCP (sin
# nombre corto elegido, ej. "project-b68c032a-000b-4601-8bd", 31 caracteres)
# hace que "${project_id}-${entorno}-grafana-provisioning" supere el
# límite y el `apply` falle con "name value must contain 3-63 characters" —
# encontrado desplegando contra ese proyecto real (2026-09-22). Se
# reemplaza el prefijo de `project_id` (largo variable, no acotado) por un
# sufijo corto y estable de `random_id`, que solo necesita ser único dentro
# de GCS, no legible.
resource "random_id" "grafana_bucket_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "grafana_provisioning" {
  name                        = "${var.entorno}-grafana-provisioning-${random_id.grafana_bucket_suffix.hex}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true # PoC — sin protección contra borrado accidental

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "grafana_lee_bucket" {
  bucket = google_storage_bucket.grafana_provisioning.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.grafana.email}"
}

resource "google_storage_bucket_object" "datasource" {
  name    = "datasources/datasource.yaml"
  bucket  = google_storage_bucket.grafana_provisioning.name
  content = templatefile("${path.module}/templates/datasource.yaml", { project_id = var.project_id })
}

resource "google_storage_bucket_object" "dashboards_provider" {
  name    = "dashboards/dashboards-provider.yaml"
  bucket  = google_storage_bucket.grafana_provisioning.name
  content = file("${path.module}/templates/dashboards-provider.yaml")
}

resource "google_storage_bucket_object" "dashboard" {
  name   = "dashboards/files/dashboard.json"
  bucket = google_storage_bucket.grafana_provisioning.name
  content = templatefile("${path.module}/dashboard.json", {
    project_id     = var.project_id
    datasource_uid = "gcm" # ver templates/datasource.yaml, uid: gcm
  })
}

resource "random_password" "grafana_admin" {
  length  = 24
  special = false
}

resource "google_secret_manager_secret" "grafana_admin_password" {
  secret_id = "${var.entorno}-grafana-admin-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "grafana_admin_password" {
  secret      = google_secret_manager_secret.grafana_admin_password.id
  secret_data = random_password.grafana_admin.result
}

resource "google_secret_manager_secret_iam_member" "grafana_lee_admin_password" {
  secret_id = google_secret_manager_secret.grafana_admin_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.grafana.email}"
}

resource "google_cloud_run_v2_service" "grafana" {
  name     = "${var.entorno}-grafana"
  location = var.region

  template {
    service_account = google_service_account.grafana.email

    # session_affinity + min_instance_count=1: Grafana guarda la sesión de
    # login en su SQLite LOCAL (sin Cloud SQL, ver limitación de
    # persistencia documentada arriba) -- con min=0 y sin afinidad, cada
    # request podía caer en una instancia distinta (o una nueva tras
    # scale-to-zero) que no conoce el token de sesión, y Grafana redirige
    # al login. Con esto, un mismo navegador siempre vuelve a la misma
    # instancia y esa instancia no se recicla por inactividad.
    session_affinity = true

    scaling {
      min_instance_count = 1
      max_instance_count = 2
    }

    containers {
      # ":latest" tal como lo pide la tarea. Nota honesta: esto hace el
      # despliegue no reproducible (una nueva versión de la imagen puede
      # cambiar de comportamiento entre un apply y otro) -- si el equipo
      # prefiere reproducibilidad, fijar un tag concreto (ej. "11.2.0") es
      # un cambio de una sola línea.
      image = "docker.io/grafana/grafana:latest"

      # Sin esto, Cloud Run usa el default de 512Mi -- insuficiente para
      # Grafana 11.x (el nuevo apiserver/unified-storage + indexado bleve
      # en memoria de dashboards/folders/playlists). Confirmado en logs
      # reales: "Out-of-memory event detected in container" repetido cada
      # pocos minutos, causando que el contenedor se reinicie a media
      # sesión -- eso es lo que se veía como "me desloguea" y "no data"
      # (no era un problema de session_affinity ni de las queries).
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      ports {
        container_port = 3000 # puerto default de la imagen oficial de Grafana
      }

      env {
        name  = "GF_SECURITY_ADMIN_USER"
        value = "admin"
      }
      env {
        name = "GF_SECURITY_ADMIN_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.grafana_admin_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "GF_AUTH_ANONYMOUS_ENABLED"
        value = "false"
      }
      env {
        # El plugin de Cloud Logging no viene en la imagen oficial de
        # Grafana — se descarga de grafana.com en el arranque del
        # contenedor. Es lo que habilita ver logs (jsonPayload.evento,
        # verificacion_id, trabajo_id) dentro de Grafana, no solo métricas.
        name  = "GF_INSTALL_PLUGINS"
        value = "googlecloud-logging-datasource"
      }
      env {
        # Explícito, aunque coincide con el default de la imagen oficial
        # -- así el volumen GCS montado abajo en la MISMA ruta no depende
        # de que ese default nunca cambie entre versiones de la imagen.
        name  = "GF_PATHS_PROVISIONING"
        value = "/etc/grafana/provisioning"
      }

      volume_mounts {
        name       = "provisioning"
        mount_path = "/etc/grafana/provisioning"
      }
    }

    volumes {
      name = "provisioning"
      gcs {
        bucket    = google_storage_bucket.grafana_provisioning.name
        read_only = true
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_storage_bucket_object.datasource,
    google_storage_bucket_object.dashboards_provider,
    google_storage_bucket_object.dashboard,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "grafana_publico" {
  name     = google_cloud_run_v2_service.grafana.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers" # PoC — la autenticación real la da el login propio de Grafana (admin/secret de arriba), ver mismo criterio en proveedores/infra/cloudrun.tf
}
