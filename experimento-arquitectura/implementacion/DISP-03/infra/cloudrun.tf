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
      # min_instance_count=1: CP-7 (plan.md) mide la latencia de ACEPTACIÓN
      # del POST /verificaciones bajo ráfaga (30 concurrentes). Con
      # min_instance_count=0 la primera ráfaga tras inactividad paga cold
      # start (arranque de contenedor + Base.metadata.create_all contra
      # Cloud SQL) dentro de la propia medición, lo cual no es la latencia
      # de "aceptación en caliente" que el escenario de calidad busca
      # demostrar. Mantener 1 instancia caliente cuesta cómputo continuo
      # (aceptable en este PoC); si el presupuesto del experimento no lo
      # permite, la alternativa es recalibrar el umbral del test para
      # incluir cold start, pero esa es una decisión de diseño de
      # experimento (disenador-escenarios/experimento-runner), no de infra.
      min_instance_count = 1
      max_instance_count = 10 # auto-scaling horizontal — ver ESC-01/ESC-03
    }

    # Explícito en vez de dejarlo en el default de la API (hoy aparecía
    # como "known after apply") — 80 es el default de Cloud Run v2, lo
    # fijamos para que una sola instancia caliente pueda absorber los 30
    # POST concurrentes de CP-7 sin forzar scale-out (= sin cold starts
    # adicionales a mitad de la ráfaga).
    max_instance_request_concurrency = 80

    containers {
      image   = local.imagen_app
      command = ["uvicorn"]
      args    = ["app.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

      resources {
        # Backstop para cuando sí haga falta escalar más allá de la
        # instancia caliente (ej. picos por encima de max_instance_count
        # actual): arranque con CPU boosteada en vez de la asignación
        # default, para acotar cuánto añade cada cold start remanente.
        startup_cpu_boost = true
      }

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
      # min_instance_count=1: CP-2 (plan.md) crea 1 verificación lenta +
      # 5 rápidas casi simultáneas vía suscripción push. Con
      # min_instance_count=0, Pub/Sub entrega los 6 mensajes en ráfaga
      # contra un worker frío: Cloud Run puede levantar varias instancias
      # nuevas en paralelo para absorber la ráfaga, y cada una paga su
      # propio cold start (arranque uvicorn + create_all contra Cloud SQL)
      # DENTRO de la ventana que el test mide — eso explica una duración
      # dominada por arranque de contenedor, no por bloqueo real del
      # procesamiento (que sí es concurrente a nivel de aplicación: cada
      # request push corre como su propia task de asyncio y
      # procesar_verificacion() usa httpx.AsyncClient, no bloqueante — ver
      # push_handler.py). Con 1 instancia caliente, los 6 mensajes de CP-2
      # deberían resolverse sobre la misma instancia sin cold start.
      min_instance_count = 1
      max_instance_count = 20 # debe absorber picos de hasta 4x — ver DISP-02
    }

    # Explícito por la misma razón que en el servicio api: evita
    # scale-out innecesario (y sus cold starts) para ráfagas que una
    # sola instancia caliente puede atender de sobra.
    max_instance_request_concurrency = 80

    containers {
      image   = local.imagen_app
      command = ["uvicorn"]
      args    = ["app.worker.push_handler:app", "--host", "0.0.0.0", "--port", "8080"]

      resources {
        startup_cpu_boost = true
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
        # El worker SÍ publica al topic de "solicitudes": no para consumir
        # verificaciones (eso lo hace la suscripción push), sino porque
        # RegistrarIntento -> despachar() reacciona a VerificacionCompletada
        # publicando el evento de integración `proveedor.habilitado` sobre
        # este mismo topic con un routing_key propio (ver
        # PublicadorPubSub.publicar_evento en app/common/publicador.py y
        # app/application/dispatcher_eventos_dominio.py). Sin esta variable,
        # PublicadorPubSub queda con _ruta_sol=None y
        # publicar_evento()/publicar_solicitud() lanzan RuntimeError — el
        # despachador ya no deja que esa excepción tumbe la respuesta HTTP
        # (ver dispatcher_eventos_dominio.py), pero el evento de integración
        # simplemente no se publicaría, así que fijar el topic aquí sigue
        # siendo la corrección real, no solo la resiliencia alrededor de
        # ella.
        name  = "PUBSUB_TOPIC_SOLICITUDES"
        value = google_pubsub_topic.solicitudes.name
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
