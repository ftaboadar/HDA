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
      max_instance_count = 2 # auto-scaling horizontal — ver ESC-01/ESC-03
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
      env {
        # No la usa ningún comando de la API hoy (ver
        # app/api/main.py) — se pasa por simetría con
        # PUBSUB_TOPIC_FALLIDAS, que tampoco usa la API todavía.
        name  = "PUBSUB_TOPIC_EVENTOS"
        value = google_pubsub_topic.eventos_integracion.name
      }
      env {
        # No lo usa ningún comando de la API hoy — mismo criterio que
        # PUBSUB_TOPIC_EVENTOS arriba. Ver var.pulsar_service_url.
        name  = "PULSAR_SERVICE_URL"
        value = var.pulsar_service_url
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
      max_instance_count = 2 # debe absorber picos de hasta 4x — ver DISP-02
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
        # El worker necesita conocer el nombre del topic de "solicitudes"
        # únicamente porque PublicadorPubSub lo usa para construir la ruta
        # con la que valida publicar_solicitud() — el worker en sí NUNCA
        # publica a este topic (solo lo consume, vía la suscripción push
        # definida en infra/pubsub.tf). Sin esta variable, _ruta_sol queda
        # en None y publicar_solicitud() lanzaría RuntimeError si alguna
        # ruta del worker llegara a invocarla (hoy ninguna lo hace, pero
        # mantenerla fijada evita sorpresas si eso cambia).
        name  = "PUBSUB_TOPIC_SOLICITUDES"
        value = google_pubsub_topic.solicitudes.name
      }
      env {
        name  = "PUBSUB_TOPIC_FALLIDAS"
        value = google_pubsub_topic.fallidas.name
      }
      env {
        # Bug de producción corregido 2026-09-06 (ver infra/pubsub.tf,
        # sección sobre `eventos_integracion`): RegistrarIntento ->
        # despachar() reacciona a VerificacionCompletada publicando el
        # evento de INTEGRACIÓN `proveedor.habilitado` (ver
        # app/application/dispatcher_eventos_dominio.py). Antes se
        # reutilizaba PUBSUB_TOPIC_SOLICITUDES para esto, lo cual hacía que
        # ese evento le llegara al propio worker por /pubsub/push como si
        # fuera una verificación real (misma suscripción, sin filtro) y
        # reventara con KeyError('verificacion_id'). Ahora
        # PublicadorPubSub.publicar_evento publica exclusivamente a este
        # topic dedicado, que no tiene ninguna suscripción push activa.
        name  = "PUBSUB_TOPIC_EVENTOS"
        value = google_pubsub_topic.eventos_integracion.name
      }
      env {
        # Ver var.pulsar_service_url — plumbing por simetría, sin uso
        # real hoy (TRANSPORTE=pubsub sigue siendo el único transporte
        # que el worker de Proveedores implementa).
        name  = "PULSAR_SERVICE_URL"
        value = var.pulsar_service_url
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
