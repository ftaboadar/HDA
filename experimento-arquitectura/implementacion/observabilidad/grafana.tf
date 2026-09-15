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
# pueda consultar métricas reales de los 3 microservicios + DISP-03.
resource "google_project_iam_member" "grafana_monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.grafana.email}"
}

resource "google_storage_bucket" "grafana_provisioning" {
  name                        = "${var.project_id}-${var.entorno}-grafana-provisioning"
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

    scaling {
      min_instance_count = 0 # sin escenario de calidad que exija Grafana caliente
      max_instance_count = 2
    }

    containers {
      # ":latest" tal como lo pide la tarea. Nota honesta: esto hace el
      # despliegue no reproducible (una nueva versión de la imagen puede
      # cambiar de comportamiento entre un apply y otro) -- si el equipo
      # prefiere reproducibilidad, fijar un tag concreto (ej. "11.2.0") es
      # un cambio de una sola línea.
      image = "docker.io/grafana/grafana:latest"

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
  member   = "allUsers" # PoC — la autenticación real la da el login propio de Grafana (admin/secret de arriba), ver mismo criterio en DISP-03/infra/cloudrun.tf
}
