from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DATABASE_URL viene del secreto de Terraform (Cloud SQL real, ver
    # infra/service.tf); el default sqlite en memoria es solo para pruebas
    # locales sin infraestructura.
    database_url: str = "sqlite:///:memory:"
    pulsar_service_url: str = "pulsar://localhost:6650"
    pulsar_topic_trabajo_finalizado: str = (
        "persistent://hda/gestion-trabajos/trabajos.finalizado"
    )
    pulsar_topic_scoring_actualizado: str = (
        "persistent://hda/scoring/scoring.actualizado"
    )

    class Config:
        env_file = ".env"


settings = Settings()
