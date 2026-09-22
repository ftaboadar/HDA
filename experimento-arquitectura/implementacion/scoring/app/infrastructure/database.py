from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

from app.common.config import settings

Base = declarative_base()

class FotografoScoringModel(Base):
    __tablename__ = 'fotografo_scoring'

    id = Column(String(36), primary_key=True)
    fotografo_id = Column(String(36), unique=True, nullable=False)
    puntuacion_actual = Column(Float, default=0.0)
    trabajos_completados = Column(Integer, default=0)
    fecha_ultima_actualizacion = Column(DateTime)

# `settings.database_url` viene de la variable de entorno DATABASE_URL (el
# secreto de Terraform apunta a la Cloud SQL real del stack, ver
# infra/service.tf); antes este módulo ignoraba la configuración y siempre
# escribía en un sqlite fijo dentro del contenedor, así que la Cloud SQL
# provisionada nunca se usaba. El `create_all` se dispara desde el startup
# de FastAPI (app/api/main.py), no al importar este módulo.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)
