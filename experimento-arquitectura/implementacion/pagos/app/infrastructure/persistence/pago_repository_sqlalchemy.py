"""Adaptador concreto de `IPagoRepository` sobre SQLAlchemy/Postgres —
mismo principio que `trabajo_repository_sqlalchemy.py`: única pieza que
traduce entre `Pago` (dominio) y `PagoORM` (persistencia)."""

from app.common.db import SessionLocal
from app.domain.pagos.pago import Pago
from app.domain.pagos.repository import IPagoRepository
from app.domain.pagos.value_objects import (
    Dinero,
    EstadoPago,
    PagoId,
    Pasarela,
    Region,
    TrabajoId,
)
from app.infrastructure.persistence.models_db import PagoORM


def _a_dominio(fila: PagoORM) -> Pago:
    return Pago(
        id=fila.id,
        trabajo_id=TrabajoId(fila.trabajo_id),
        monto=Dinero(fila.monto, fila.moneda),
        region=Region(fila.region),
        pasarela=Pasarela(fila.pasarela),
        estado=EstadoPago(fila.estado),
        referencia_externa=fila.referencia_externa,
        motivo_falla=fila.motivo_falla,
        creado_en=fila.creado_en,
    )


class PagoRepositorySQLAlchemy(IPagoRepository):
    def guardar(self, pago: Pago) -> None:
        with SessionLocal() as sesion:
            fila = sesion.get(PagoORM, pago.id)
            if fila is None:
                fila = PagoORM(id=pago.id, creado_en=pago.creado_en)
                sesion.add(fila)

            fila.trabajo_id = pago.trabajo_id.valor
            fila.monto = pago.monto.valor
            fila.moneda = pago.monto.moneda
            fila.region = pago.region.value
            fila.pasarela = pago.pasarela.value
            fila.estado = pago.estado.value
            fila.referencia_externa = pago.referencia_externa
            fila.motivo_falla = pago.motivo_falla

            sesion.commit()

    def obtener_por_id(self, id: PagoId) -> Pago | None:
        with SessionLocal() as sesion:
            fila = sesion.get(PagoORM, id.valor)
            return _a_dominio(fila) if fila else None

    def listar_por_trabajo(self, trabajo_id: TrabajoId) -> list[Pago]:
        with SessionLocal() as sesion:
            filas = (
                sesion.query(PagoORM)
                .filter(PagoORM.trabajo_id == trabajo_id.valor)
                .all()
            )
            return [_a_dominio(f) for f in filas]
