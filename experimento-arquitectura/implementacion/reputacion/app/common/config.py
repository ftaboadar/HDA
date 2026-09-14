"""Configuración centralizada, cargada desde variables de entorno. Mismo
patrón que `DISP-03/app/common/config.py` (pydantic-settings), copiado a
propósito -- no importado -- porque cada microservicio es su propio
despliegue independiente (ver docstring de domain/seedwork/value_object.py
sobre por qué no se comparte código entre Bounded Contexts)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://hda:hda@postgres:5432/reputacion"

    # Broker de eventos: Apache Pulsar (ver
    # experimento-arquitectura/implementacion/pulsar-infra/). En local,
    # `broker:6650` asume que este servicio corre en la misma red Docker
    # que el cluster de pulsar-infra (ver docker-compose.yml de este
    # directorio); si se corre suelto, sobreescribir con localhost:6650.
    pulsar_service_url: str = "pulsar://broker:6650"
    pulsar_topic_trabajos_finalizado: str = "persistent://hda/gestion-trabajos/trabajos.finalizado"
    pulsar_subscription: str = "reputacion-trabajos-finalizado"


settings = Settings()
