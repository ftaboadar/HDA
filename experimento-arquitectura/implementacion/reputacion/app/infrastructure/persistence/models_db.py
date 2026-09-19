"""Modelos SQLAlchemy -- vocabulario de PERSISTENCIA, no de dominio (mismo
principio que `proveedores/app/common/models_db.py`: el dominio no conoce estas
clases, solo los adaptadores de `infrastructure/persistence/`).

`EventoReputacionORM` es la tabla que hace el Event Sourcing real (Regla 5,
criterio 3: persistencia real, motor de BD real detrás de un puerto) --
cada fila es UN evento de dominio ya ocurrido, nunca un estado mutable.
`TrabajoVistoORM` es la tabla de auditoría del consumidor liviano de
`trabajos.finalizado` (ver application/commands/registrar_evento_trabajo_finalizado.py)
-- deliberadamente separada de `EventoReputacionORM`, no es parte del
Event Store del agregado `PerfilReputacion`."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base


class EventoReputacionORM(Base):
    __tablename__ = "eventos_reputacion"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    agregado_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    tipo_evento: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrabajoVistoORM(Base):
    """Tabla de auditoría del consumidor liviano de `trabajos.finalizado`
    -- ver docstring de `application/commands/registrar_evento_trabajo_finalizado.py`
    sobre por qué esto NO es parte del Event Store del agregado."""

    __tablename__ = "trabajos_vistos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trabajo_id: Mapped[str] = mapped_column(String, nullable=False)
    proveedor_id: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    recibido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
