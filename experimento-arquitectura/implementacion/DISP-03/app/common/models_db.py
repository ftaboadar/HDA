"""Persistencia real (Regla 5.3 de la rúbrica): tablas `verificaciones` e
`intentos_verificacion` en Postgres local / Cloud SQL en GCP — no una
estructura en memoria.

`VerificacionORM` conserva sus columnas planas (`intentos: int`,
`motivo_falla: str`) por compatibilidad con el contrato HTTP existente
(ver 11-implementacion-ddd-verificacion.md, sección 4: "el contrato HTTP no
cambia") — pero desde que existe la capa de dominio, la fuente de verdad de
trazabilidad es `IntentoVerificacionORM` (tabla hija), que
`VerificacionRepositorySQLAlchemy` mantiene sincronizada con el agregado.
Sin migraciones formales (Alembic) en este PoC: `Base.metadata.create_all()`
en el arranque de api/worker crea la tabla nueva si no existe."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

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

    intentos_registrados = relationship(
        "IntentoVerificacionORM",
        back_populates="verificacion",
        order_by="IntentoVerificacionORM.numero",
        cascade="all, delete-orphan",
    )


class IntentoVerificacionORM(Base):
    """Entidad hija — persiste `IntentoVerificacion` (ver
    app/domain/verificacion/verificacion.py). Un registro por intento, no un
    contador plano: es la trazabilidad completa que exige DISP-03."""

    __tablename__ = "intentos_verificacion"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verificacion_id = Column(
        UUID(as_uuid=True), ForeignKey("verificaciones.id"), nullable=False, index=True
    )
    numero = Column(Integer, nullable=False)
    resultado = Column(String, nullable=False)  # EXITOSO | FALLIDO
    error = Column(Text, nullable=True)
    duracion_ms = Column(Integer, nullable=False)
    ocurrido_en = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)

    verificacion = relationship("VerificacionORM", back_populates="intentos_registrados")
