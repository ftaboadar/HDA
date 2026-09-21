"""Persistencia real (Regla 5, criterio 3): tablas `pagos` y
`trabajos_elegibles_pago` en Postgres — base de datos propia de este
microservicio (`hda_pagos`), separada de la de Gestión de Trabajos desde
que Pagos dejó de ser un submódulo ACL dentro de ese proceso. Sin
migraciones formales (Alembic) en este PoC: `Base.metadata.create_all()` en
el arranque de la API crea las tablas si no existen (mismo patrón que
Proveedores/reputación/gestión-de-trabajos).

`PagoORM.trabajo_id` ya NO es un `ForeignKey` hacia una tabla `trabajos`
local (esa tabla vive en la base de datos de Gestión de Trabajos, otro
microservicio con su propia BD) — es solo una columna UUID que referencia
por id, igual que `RegistroTrabajoElegibleORM.trabajo_id`."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.common.db import Base


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class PagoORM(Base):
    """Raíz de agregado `Pago` (dominio) persistida — `trabajo_id` es una
    referencia por id al agregado `Trabajo` de OTRO microservicio (Gestión
    de Trabajos), sin `ForeignKey` porque ya no comparten base de datos."""

    __tablename__ = "pagos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trabajo_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    monto = Column(Numeric, nullable=False)
    moneda = Column(String, nullable=False)
    region = Column(String, nullable=False)
    pasarela = Column(String, nullable=False)
    estado = Column(String, nullable=False, default="PENDIENTE", index=True)
    referencia_externa = Column(String, nullable=True)
    motivo_falla = Column(Text, nullable=True)
    creado_en = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)


class RegistroTrabajoElegibleORM(Base):
    """Tabla propia de este microservicio (Regla 5, criterio 4 — ver
    `app/application/ports/registro_trabajos.py` para la distinción
    dominio/integración y la explicación de cómo se puebla ahora vía
    `POST /pagos`, no vía dispatcher intra-proceso como antes de la
    separación)."""

    __tablename__ = "trabajos_elegibles_pago"

    trabajo_id = Column(UUID(as_uuid=True), primary_key=True)
    proveedor_id = Column(String, nullable=False)
    monto = Column(Numeric, nullable=False)
    moneda = Column(String, nullable=False)
    region = Column(String, nullable=False)


class TransaccionORM(Base):
    __tablename__ = "transacciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pago_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tipo = Column(String, nullable=False) # RETENCION, LIBERACION, COMPENSACION
    estado = Column(String, nullable=False) # EXITOSA, FALLIDA
    fecha = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)
