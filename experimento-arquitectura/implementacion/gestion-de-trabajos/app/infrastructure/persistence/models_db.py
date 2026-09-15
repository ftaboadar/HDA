"""Persistencia real (Regla 5, criterio 3): tablas `trabajos` y `pagos` en
Postgres — misma base de datos, un microservicio (ver 12-plan-entrega-4.md
sección 5: "Pagos no aporta una BD propia al conteo"). Sin migraciones
formales (Alembic) en este PoC: `Base.metadata.create_all()` en el arranque
de la API crea las tablas si no existen (mismo patrón que DISP-03)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

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

    pagos = relationship(
        "PagoORM", back_populates="trabajo", cascade="all, delete-orphan"
    )


class PagoORM(Base):
    """Tabla del submódulo ACL de Pagos — `trabajo_id` referencia
    `trabajos.id` porque comparten base de datos (mismo microservicio), no
    porque `Pago` sea una entidad hija del agregado `Trabajo`: son dos
    raíces de agregado independientes (ver domain/pagos/pago.py)."""

    __tablename__ = "pagos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trabajo_id = Column(
        UUID(as_uuid=True), ForeignKey("trabajos.id"), nullable=False, index=True
    )
    monto = Column(Numeric, nullable=False)
    moneda = Column(String, nullable=False)
    region = Column(String, nullable=False)
    pasarela = Column(String, nullable=False)
    estado = Column(String, nullable=False, default="PENDIENTE", index=True)
    referencia_externa = Column(String, nullable=True)
    motivo_falla = Column(Text, nullable=True)
    creado_en = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)

    trabajo = relationship("TrabajoORM", back_populates="pagos")


class RegistroTrabajoElegibleORM(Base):
    """Tabla propia del módulo ACL de Pagos (Regla 5, criterio 4) — poblada
    ÚNICAMENTE por `application/dispatcher_eventos_dominio.py` al reaccionar
    al evento de dominio `TrabajoFinalizado`, nunca por una lectura directa
    de `trabajos`. Es el registro que le permite a `PagarTrabajo` dejar de
    depender de `ITrabajoRepository` (ver
    app/application/ports/registro_trabajos.py)."""

    __tablename__ = "trabajos_elegibles_pago"

    trabajo_id = Column(UUID(as_uuid=True), primary_key=True)
    proveedor_id = Column(String, nullable=False)
    monto = Column(Numeric, nullable=False)
    moneda = Column(String, nullable=False)
    region = Column(String, nullable=False)
