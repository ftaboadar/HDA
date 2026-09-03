# Equivalente GCP del bus de eventos local (RabbitMQ, ver ../app/common/mq.py).
# El topic "solicitudes" es el evento de integración "gordo" (verificacion_id,
# proveedor_id, tipo_verificador) que la API publica y el worker consume vía
# suscripción push. El topic "fallidas" es la DLQ que exige DISP-03.

resource "google_pubsub_topic" "solicitudes" {
  name       = "${var.entorno}-verificacion-solicitudes"
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "fallidas" {
  name       = "${var.entorno}-verificacion-fallidas" # DLQ
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "solicitudes_push" {
  name  = "${var.entorno}-verificacion-solicitudes-push"
  topic = google_pubsub_topic.solicitudes.name

  ack_deadline_seconds = 30

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.worker.uri}/pubsub/push"
    oidc_token {
      service_account_email = google_service_account.invocador_pubsub.email
    }
  }

  # Dead-letter a nivel de infraestructura, como respaldo del manejo de DLQ
  # que ya hace la aplicación en worker/core.py tras agotar sus propios
  # reintentos — ver README.md, sección "Dos capas de reintento".
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.fallidas.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "20s"
  }
}

# Suscripción pull sobre la DLQ: el reproceso manual (POST /dlq/{id}/reprocesar
# en la API, o un job de Cloud Run activado manualmente) la consume.
resource "google_pubsub_subscription" "fallidas_pull" {
  name  = "${var.entorno}-verificacion-fallidas-pull"
  topic = google_pubsub_topic.fallidas.name

  ack_deadline_seconds = 30
}

# El service account gestionado de Pub/Sub necesita permiso explícito para
# publicar en el topic de DLQ cuando reenvía mensajes muertos.
resource "google_pubsub_topic_iam_member" "dlq_recibe_desde_pubsub_gestionado" {
  topic  = google_pubsub_topic.fallidas.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.actual.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
