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

# Bug de producción (2026-09-06, GCP real `hda-projectt`): antes de este
# topic, `PublicadorPubSub.publicar_evento` (usado por
# app/application/dispatcher_eventos_dominio.py para publicar el evento de
# INTEGRACIÓN `proveedor.habilitado` cuando una verificación deja a un
# proveedor elegible) reutilizaba el topic "solicitudes" de arriba,
# distinguiendo el mensaje solo por un campo `routing_key` dentro del propio
# JSON. Como `solicitudes_push` (abajo) está suscrita a ESE topic sin
# ningún filtro, cada `proveedor.habilitado` le llegaba al worker por
# /pubsub/push como si fuera una solicitud de verificación real, y
# `push_handler.py` reventaba con `KeyError: 'verificacion_id'` — Pub/Sub
# reintregaba el mismo mensaje envenenado hasta agotar
# `max_delivery_attempts`, compitiendo por capacidad del worker con
# verificaciones reales. RabbitMQ no sufre esto porque la cola local está
# bindeada solo a routing keys `verificacion.*` (ver
# app/common/mq.py/PublicadorRabbitMQ.publicar_evento): un mensaje con
# routing_key "proveedor.habilitado" queda sin enrutar por diseño, nunca
# llega al consumidor. Pub/Sub no tiene ese enrutamiento por routing key a
# nivel de suscripción, así que la corrección es un topic dedicado.
#
# Deliberadamente SIN suscripción todavía: ningún bounded context de este
# PoC consume `proveedor.habilitado` (los consumidores reales — Marketplace,
# Siniestros, Suscripciones — están fuera del alcance de DISP-03, ver
# docstring de Publicador.publicar_evento). Publicar a un topic sin
# suscripción es válido en Pub/Sub (el mensaje simplemente no se retiene
# para nadie) y es el equivalente exacto del "mensaje sin enrutar por
# diseño" que ya describe PublicadorRabbitMQ.publicar_evento.
resource "google_pubsub_topic" "eventos_integracion" {
  name       = "${var.entorno}-verificacion-eventos-integracion"
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
