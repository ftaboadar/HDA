from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///:memory:"
    pulsar_service_url: str = "pulsar://localhost:6650"
    pulsar_topic_siniestro_aprobado: str = "persistent://hda/siniestros/siniestro.aprobado"
    pulsar_topic_decision_partner: str = "persistent://hda/siniestros/decision.partner"
    pulsar_topic_solicitar_aprobacion_novedad: str = "persistent://hda/siniestros/solicitar.aprobacion.novedad"
    
    class Config:
        env_file = ".env"

settings = Settings()
