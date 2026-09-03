"""Configuración centralizada, cargada desde variables de entorno.

Los valores por defecto asumen el entorno local (docker-compose). En GCP, cada
variable se sobreescribe vía las env vars que Terraform inyecta en Cloud Run
(ver ../../infra/cloudrun.tf).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Transporte de mensajería: "rabbitmq" (local) o "pubsub" (GCP)
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

    mock_policia_url: str = "http://mock-policia:8000"
    mock_rues_url: str = "http://mock-rues:8000"
    mock_certificadora_url: str = "http://mock-certificadora:8000"

    max_reintentos: int = 4
    timeout_externo_s: float = 3.0
    backoff_base_s: float = 0.5
    backoff_max_s: float = 8.0


settings = Settings()
