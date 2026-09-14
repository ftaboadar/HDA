"""Topología de Apache Pulsar para Proveedores (sección 2.2, punto 2 del plan
de Entrega 4, `experimento-arquitectura/contexto/12-plan-entrega-4.md`).

A diferencia de `mq.py` (RabbitMQ), en Pulsar los tópicos no requieren
declaración explícita de topología — se auto-provisionan, o se crean por
adelantado vía Terraform/Helm contra el cluster real (ver
`implementacion/pulsar-infra/`, propiedad de Daniel dentro del reparto de la
sección 8 del plan). Lo que sí hay que fijar por convención, aquí mismo, es:
el namespace, los nombres de los 3 tópicos de aplicación (mismos 3 destinos
físicos que ya existían para RabbitMQ/Pub-Sub, ver `publicador.py`), y la
política de Dead Letter NATIVA de la suscripción del worker.

CUIDADO explícito (mismo bug de producción del 2026-09-06 contra GCP real,
ver `publicador.py` y `README.md`): `TOPIC_EVENTOS` (eventos de integración,
ej. `proveedor.habilitado`) debe seguir siendo FÍSICAMENTE DISTINTO de
`TOPIC_SOLICITUDES` — la suscripción del worker (`worker/pulsar_consumer.py`)
solo está atada a `TOPIC_SOLICITUDES`, así que un evento de integración
publicado por error sobre ese tópico volvería a producir el mismo
`KeyError('verificacion_id')` en el consumidor, ahora con Pulsar en vez de
Pub/Sub."""

from __future__ import annotations

NAMESPACE = "persistent://hda/proveedores"

TOPIC_SOLICITUDES = f"{NAMESPACE}/verificacion.solicitudes"
TOPIC_FALLIDAS = f"{NAMESPACE}/verificacion.fallida-dlq"
# Tópico de eventos de INTEGRACIÓN (ej. proveedor.habilitado) — ver el
# cuidado explícito en el docstring del módulo.
TOPIC_EVENTOS = f"{NAMESPACE}/proveedor.habilitado"

# Tópico técnico donde Pulsar deposita, vía DeadLetterPolicy nativa, los
# mensajes que agotaron `max_redeliver_count` SIN que nuestro propio código
# alcanzara a procesarlos (ej. el worker revienta a mitad de un mensaje por
# una excepción no controlada, o la BD está caída). Es una "DLQ" distinta,
# a nivel de infraestructura, de `TOPIC_FALLIDAS` — que es donde
# `publicar_fallida()` escribe cuando `procesar_verificacion()` sí corrió
# de punta a punta y agotó SUS PROPIOS reintentos internos con éxito (el
# mensaje se procesó, el resultado fue definitivamente fallido). Ver
# docstring de `app/worker/job_reproceso_dlq.py`, que monitorea la segunda,
# no la primera.
TOPIC_SOLICITUDES_DLQ_NATIVO = f"{NAMESPACE}/verificacion.solicitudes-dlq-nativo"

# Namespace de Gestión de Trabajos (Frans, sección 8 del plan) — Proveedores
# solo CONSUME de ahí (sección 2.1: "comunicación real en ambos sentidos"),
# nunca publica ni administra su topología.
TOPIC_TRABAJOS_FINALIZADO = "persistent://hda/trabajos/trabajos.finalizado"


def construir_dead_letter_policy(max_redeliver_count: int = 3):
    """Política de Dead Letter nativa de Pulsar para la suscripción del
    worker (`worker/pulsar_consumer.py`) — la red de seguridad de
    infraestructura, análoga al DLX de RabbitMQ (`mq.py`) y al
    `dead_letter_policy` de la suscripción push de Pub/Sub
    (`infra/pubsub.tf`).

    Import perezoso de `pulsar`: así este módulo (y sus constantes de
    nombres de tópico) se puede importar desde tests unitarios o desde
    `app/common/config.py` sin requerir el cliente de Pulsar instalado en
    cada entorno (ej. CI corriendo solo contra RabbitMQ/Pub-Sub)."""
    import pulsar

    return pulsar.ConsumerDeadLetterPolicy(
        max_redeliver_count=max_redeliver_count,
        dead_letter_topic=TOPIC_SOLICITUDES_DLQ_NATIVO,
    )
