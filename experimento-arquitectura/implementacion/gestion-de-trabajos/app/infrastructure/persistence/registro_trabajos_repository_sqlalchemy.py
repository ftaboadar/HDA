"""Adaptador concreto de `IRegistroTrabajosRepository` sobre
SQLAlchemy/Postgres — única pieza que traduce entre `RegistroTrabajoElegible`
(puerto de aplicación) y `RegistroTrabajoElegibleORM` (persistencia). Mismo
principio que `pago_repository_sqlalchemy.py` / `trabajo_repository_sqlalchemy.py`."""

from app.application.ports.registro_trabajos import (
    IRegistroTrabajosRepository,
    RegistroTrabajoElegible,
)
from app.common.db import SessionLocal
from app.domain.trabajo.value_objects import ProveedorId, Region, TrabajoId
from app.infrastructure.persistence.models_db import RegistroTrabajoElegibleORM


def _a_dominio(fila: RegistroTrabajoElegibleORM) -> RegistroTrabajoElegible:
    return RegistroTrabajoElegible(
        trabajo_id=TrabajoId(fila.trabajo_id),
        proveedor_id=ProveedorId(fila.proveedor_id),
        monto=fila.monto,
        moneda=fila.moneda,
        region=Region(fila.region),
    )


class RegistroTrabajosRepositorySQLAlchemy(IRegistroTrabajosRepository):
    def guardar(self, registro: RegistroTrabajoElegible) -> None:
        with SessionLocal() as sesion:
            fila = sesion.get(RegistroTrabajoElegibleORM, registro.trabajo_id.valor)
            if fila is None:
                fila = RegistroTrabajoElegibleORM(trabajo_id=registro.trabajo_id.valor)
                sesion.add(fila)

            fila.proveedor_id = str(registro.proveedor_id)
            fila.monto = registro.monto
            fila.moneda = registro.moneda
            fila.region = registro.region.value

            sesion.commit()

    def obtener_por_trabajo(
        self, trabajo_id: TrabajoId
    ) -> RegistroTrabajoElegible | None:
        with SessionLocal() as sesion:
            fila = sesion.get(RegistroTrabajoElegibleORM, trabajo_id.valor)
            return _a_dominio(fila) if fila else None
