"""Persistencia real (Regla 5, criterio 3): tabla `trabajos` en Postgres.
Sin migraciones formales (Alembic) en este PoC: `Base.metadata.create_all()`
en el arranque de la API crea las tablas si no existen (mismo patrón que
DISP-03).

Separación de Pagos (ver `implementacion/pagos/README.md`): la tabla
`pagos` (agregado `Pago`) se movió a la base de datos propia de ese
microservicio (`hda_pagos`) — ya no vive aquí. `trabajos_elegibles_pago` se
queda: sigue siendo un registro propio de ESTE servicio, poblado por
`application/dispatcher_eventos_dominio.py` al reaccionar al evento de
dominio `TrabajoFinalizado`; el microservicio Pagos ya no lo lee (recibe
esos mismos datos por HTTP en `POST /pagos`, ver README.md de ese
servicio), pero se conserva aquí como trazabilidad local de qué trabajos
finalizaron y en qué términos."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.common.db import Base


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class TrabajoORM(Base):
    __tablename__ = "trabajos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id = Column(String, nullable=False, index=True)
    estado = Column(String, nullable=False, default="PENDIENTE", index=True)
    monto = Column(Numeric, nullable=False)
    moneda = Column(String, nullable=False)
    region = Column(String, nullable=False, index=True)
    fecha_creacion = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)


class RegistroTrabajoElegibleORM(Base):
    """Tabla propia de este servicio (Regla 5, criterio 4) — poblada
    ÚNICAMENTE por `application/dispatcher_eventos_dominio.py` al reaccionar
    al evento de dominio `TrabajoFinalizado`, nunca por una lectura directa
    de `trabajos`. Antes de la separación de Pagos, era el registro que le
    permitía a `PagarTrabajo` (en ese entonces submódulo de este mismo
    proceso) dejar de depender de `ITrabajoRepository` (ver
    app/application/ports/registro_trabajos.py); ahora Pagos es un
    microservicio aparte y recibe esos mismos datos por HTTP, pero el
    registro local se conserva como trazabilidad."""

    __tablename__ = "trabajos_elegibles_pago"

    trabajo_id = Column(UUID(as_uuid=True), primary_key=True)
    proveedor_id = Column(String, nullable=False)
    monto = Column(Numeric, nullable=False)
    moneda = Column(String, nullable=False)
    region = Column(String, nullable=False)
