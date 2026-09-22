"""Adaptador concreto de `ITrabajoRepository` sobre SQLAlchemy/Postgres —
único punto del sistema que traduce entre el lenguaje del dominio
(`Trabajo`, VOs) y el de persistencia (`TrabajoORM`). Ni `api/`, ni
`application/`, ni `domain/` conocen SQLAlchemy."""

from app.common.db import SessionLocal
from app.ciclo_vida.domain.repository import ITrabajoRepository
from app.ciclo_vida.domain.trabajo import Trabajo
from app.ciclo_vida.domain.value_objects import (
    Dinero,
    EstadoTrabajo,
    ProveedorId,
    Region,
    TrabajoId,
)
from app.infrastructure.persistence.models_db import TrabajoORM


def _a_dominio(fila: TrabajoORM) -> Trabajo:
    return Trabajo(
        id=fila.id,
        proveedor_id=ProveedorId(fila.proveedor_id),
        monto=Dinero(fila.monto, fila.moneda),
        region=Region(fila.region),
        estado=EstadoTrabajo(fila.estado),
        fecha_creacion=fila.fecha_creacion,
    )


class TrabajoRepositorySQLAlchemy(ITrabajoRepository):
    def guardar(self, trabajo: Trabajo) -> None:
        with SessionLocal() as sesion:
            fila = sesion.get(TrabajoORM, trabajo.id)
            if fila is None:
                fila = TrabajoORM(id=trabajo.id, fecha_creacion=trabajo.fecha_creacion)
                sesion.add(fila)

            fila.proveedor_id = str(trabajo.proveedor_id)
            fila.estado = trabajo.estado.value
            fila.monto = trabajo.monto.valor
            fila.moneda = trabajo.monto.moneda
            fila.region = trabajo.region.value

            sesion.commit()

    def obtener_por_id(self, id: TrabajoId) -> Trabajo | None:
        with SessionLocal() as sesion:
            fila = sesion.get(TrabajoORM, id.valor)
            return _a_dominio(fila) if fila else None
