from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg2://hda:hda@postgres:5432/suscripciones"
    pulsar_service_url: str = "pulsar://localhost:6650"
    pulsar_topic_trabajos_finalizado: str = (
        "persistent://hda/gestion-trabajos/trabajos.finalizado"
    )
    pulsar_topic_ciclo_suscripcion: str = (
        "persistent://hda/suscripciones/suscripciones.ciclo_suscripcion"
    )
    pulsar_subscription: str = "suscripciones-trabajos-finalizado"


settings = Settings()
