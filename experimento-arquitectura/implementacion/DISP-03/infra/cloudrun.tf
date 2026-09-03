# Una sola imagen compartida (api, worker y mocks arrancan comandos uvicorn
# distintos sobre el mismo artefacto) — igual que docker-compose.yml usa un
# solo Dockerfile para los 5 servicios locales.

locals {
  imagen_app = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.hda.repository_id}/hda-disp03:latest"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "${var.entorno}-api"
  location = var.region

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10 # auto-scaling horizontal — ver ESC-01/ESC-03
    }

    containers {
      image   = local.imagen_app
      command = ["uvicorn"]
      args    = ["app.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

      env {
        name  = "TRANSPORTE"
        value = "pubsub"
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "PUBSUB_TOPIC_SOLICITUDES"
        value = google_pubsub_topic.solicitudes.name
      }
      env {
        name  = "PUBSUB_TOPIC_FALLIDAS"
        value = google_pubsub_topic.fallidas.name
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.verificacion.connection_name]
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service" "worker" {
  name     = "${var.entorno}-worker"
  location = var.region

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 20 # debe absorber picos de hasta 4x — ver DISP-02
    }

    containers {
      image   = local.imagen_app
      command = ["uvicorn"]
      args    = ["app.worker.push_handler:app", "--host", "0.0.0.0", "--port", "8080"]

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "PUBSUB_TOPIC_FALLIDAS"
        value = google_pubsub_topic.fallidas.name
      }
      env {
        name  = "MAX_REINTENTOS"
        value = tostring(var.max_reintentos)
      }
      env {
        name  = "TIMEOUT_EXTERNO_S"
        value = tostring(var.timeout_externo_s)
      }
      env {
        name  = "MOCK_POLICIA_URL"
        value = google_cloud_run_v2_service.mock["policia"].uri
      }
      env {
        name  = "MOCK_RUES_URL"
        value = google_cloud_run_v2_service.mock["rues"].uri
      }
      env {
        name  = "MOCK_CERTIFICADORA_URL"
        value = google_cloud_run_v2_service.mock["certificadora"].uri
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.verificacion.connection_name]
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "publico_api" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers" # PoC — restringir con IAM real antes de un entorno productivo
}
