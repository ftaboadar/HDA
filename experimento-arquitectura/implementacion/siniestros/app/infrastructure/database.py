from sqlalchemy import create_engine, Column, String, Float, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

from app.common.config import settings

# `settings.database_url` viene de la variable de entorno DATABASE_URL (el
# secreto de Terraform apunta a la Cloud SQL real del stack, ver
# infra/service.tf); el default sqlite en memoria de app/common/config.py
# es solo para pruebas locales sin infraestructura. Antes este módulo
# ignoraba la configuración y siempre escribía en un sqlite efímero dentro
# del contenedor, así que la Cloud SQL provisionada nunca se usaba.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SiniestroModel(Base):
    __tablename__ = "siniestros"
    id = Column(String, primary_key=True, index=True)
    cliente_id = Column(String, index=True)
    monto_reclamado = Column(Float)
    estado = Column(String)
    reserva = Column(Float)
    facturas = Column(JSON)
