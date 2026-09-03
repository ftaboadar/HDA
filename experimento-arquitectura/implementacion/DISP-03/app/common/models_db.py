"""Persistencia real (Regla 5.3 de la rúbrica): tabla `verificaciones` en
Postgres local / Cloud SQL en GCP — no una estructura en memoria."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.common.db import Base


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class VerificacionORM(Base):
    __tablename__ = "verificaciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id = Column(String, nullable=False, index=True)
    tipo_verificador = Column(String, nullable=False, index=True)  # policia | rues | certificadora
    estado = Column(String, nullable=False, default="PENDIENTE", index=True)
    intentos = Column(Integer, nullable=False, default=0)
    motivo_falla = Column(Text, nullable=True)
    creado_en = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)
    actualizado_en = Column(
        DateTime(timezone=True), default=_ahora_utc, onupdate=_ahora_utc, nullable=False
    )
    completado_en = Column(DateTime(timezone=True), nullable=True)
    en_dlq_desde = Column(DateTime(timezone=True), nullable=True)
    reprocesos = Column(Integer, nullable=False, default=0)
