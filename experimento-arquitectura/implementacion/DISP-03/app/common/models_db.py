"""Persistencia real (Regla 5.3 de la rúbrica): tabla `verificaciones` en
Postgres local / Cloud SQL en GCP — no una estructura en memoria."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.common.db import Base


class VerificacionORM(Base):
    __tablename__ = "verificaciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id = Column(String, nullable=False, index=True)
    tipo_verificador = Column(String, nullable=False, index=True)  # policia | rues | certificadora
    estado = Column(String, nullable=False, default="PENDIENTE", index=True)
    intentos = Column(Integer, nullable=False, default=0)
    motivo_falla = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    completado_en = Column(DateTime, nullable=True)
    en_dlq_desde = Column(DateTime, nullable=True)
    reprocesos = Column(Integer, nullable=False, default=0)
