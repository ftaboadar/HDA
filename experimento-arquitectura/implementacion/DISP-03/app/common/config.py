"""Configuración centralizada, cargada desde variables de entorno.

Los valores por defecto asumen el entorno local (docker-compose). En GCP, cada
variable se sobreescribe vía las env vars que Terraform inyecta en Cloud Run
(ver ../../infra/cloudrun.tf).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.common import pulsar_topology


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Transporte de mensajería: "rabbitmq" (local), "pubsub" (GCP) o "pulsar"
    # (cluster de Apache Pulsar, ver implementacion/pulsar-infra/ y sección
    # 2.2 del plan de Entrega 4)
    transporte: str = "rabbitmq"

    database_url: str = "postgresql+psycopg2://hda:hda@postgres:5432/verificacion"

    rabbitmq_url: str = "amqp://hda:hda@rabbitmq:5672/"
    exchange_solicitudes: str = "verificacion.exchange"
    cola_solicitudes: str = "verificacion.solicitudes"
    exchange_dlq: str = "verificacion.dlx"
    cola_dlq: str = "verificacion.fallidas"

    gcp_project: str = ""
    pubsub_topic_solicitudes: str = ""
    pubsub_topic_fallidas: str = ""
    # Topic dedicado a eventos de INTEGRACIÓN (ej. proveedor.habilitado) —
    # separado del topic de solicitudes desde el bug de producción del
    # 2026-09-06 (ver infra/pubsub.tf y app/common/publicador.py). Nunca
    # reutilizar pubsub_topic_solicitudes para esto: la suscripción push del
    # worker está atada a ese topic y no filtra por tipo de mensaje.
    pubsub_topic_eventos: str = ""

    # --- Pulsar (transporte "pulsar", ver app/common/pulsar_topology.py y
    # sección 2.2 del plan de Entrega 4) — mismo patrón 1:1 de nombres que
    # el bloque pubsub_* de arriba, para no romper la simetría que hace
    # legible el resto del código.
    pulsar_service_url: str = "pulsar://pulsar:6650"
    pulsar_admin_url: str = "http://pulsar:8080"
    pulsar_topic_solicitudes: str = pulsar_topology.TOPIC_SOLICITUDES
    pulsar_topic_fallidas: str = pulsar_topology.TOPIC_FALLIDAS
    # Topic dedicado a eventos de INTEGRACIÓN (ej. proveedor.habilitado) —
    # mismo cuidado que pubsub_topic_eventos: NUNCA reutilizar
    # pulsar_topic_solicitudes para esto (bug de producción 2026-09-06, ver
    # app/common/publicador.py y app/common/pulsar_topology.py).
    pulsar_topic_eventos: str = pulsar_topology.TOPIC_EVENTOS
    pulsar_suscripcion_solicitudes: str = "verificacion-solicitudes-worker"

    # Consumidor liviano de `trabajos.finalizado` (Gestión de Trabajos ->
    # Proveedores, sección 2 punto 2 y sección 1.1 del plan de Entrega 4) —
    # namespace ajeno, propiedad de Gestión de Trabajos; Proveedores solo lo
    # consume, nunca administra esa topología.
    pulsar_topic_trabajos_finalizado: str = pulsar_topology.TOPIC_TRABAJOS_FINALIZADO
    pulsar_suscripcion_trabajos_finalizado: str = "proveedores-trabajos-finalizado"

    # Job de reproceso automático de la DLQ vía la API de estadísticas de
    # Pulsar (sección 2, punto 3 del plan de Entrega 4) — dispara
    # ReprocesarDesdeDLQ cuando el backlog de pulsar_topic_fallidas supera
    # este umbral, en vez de un cron ciego por tiempo fijo.
    pulsar_dlq_backlog_umbral: int = 50
    pulsar_dlq_check_interval_s: float = 30.0

    mock_policia_url: str = "http://mock-policia:8000"
    mock_rues_url: str = "http://mock-rues:8000"
    mock_certificadora_url: str = "http://mock-certificadora:8000"

    max_reintentos: int = 4
    timeout_externo_s: float = 3.0
    backoff_base_s: float = 0.5
    backoff_max_s: float = 8.0


settings = Settings()
