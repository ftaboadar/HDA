"""Adaptador concreto de `INovedadRepository` sobre SQLAlchemy/Postgres —
único punto del sistema que traduce entre el lenguaje del dominio
(`Novedad`, VOs) y el de persistencia (`NovedadORM`). Mismo patrón que
`trabajo_repository_sqlalchemy.py`; ni `api/`, ni `application/`, ni
`domain/` conocen SQLAlchemy."""

from app.common.db import SessionLocal
from app.domain.novedades.novedad import Novedad
from app.domain.novedades.repository import INovedadRepository
from app.domain.novedades.value_objects import EstadoNovedad, NovedadId
from app.domain.trabajo.value_objects import TrabajoId
from app.infrastructure.persistence.models_db import NovedadORM


def _a_dominio(fila: NovedadORM) -> Novedad:
    return Novedad(
        id=fila.id,
        trabajo_id=TrabajoId(fila.trabajo_id),
        descripcion=fila.descripcion,
        estado=EstadoNovedad(fila.estado),
        intentos=fila.intentos,
        creado_en=fila.creado_en,
    )


class NovedadRepositorySQLAlchemy(INovedadRepository):
    def guardar(self, novedad: Novedad) -> None:
        with SessionLocal() as sesion:
            fila = sesion.get(NovedadORM, novedad.id)
            if fila is None:
                fila = NovedadORM(id=novedad.id, creado_en=novedad.creado_en)
                sesion.add(fila)

            fila.trabajo_id = novedad.trabajo_id.valor
            fila.descripcion = novedad.descripcion
            fila.estado = novedad.estado.value
            fila.intentos = novedad.intentos

            sesion.commit()

    def obtener_por_id(self, id: NovedadId) -> Novedad | None:
        with SessionLocal() as sesion:
            fila = sesion.get(NovedadORM, id.valor)
            return _a_dominio(fila) if fila else None

    def listar_pendientes(self) -> list[Novedad]:
        with SessionLocal() as sesion:
            filas = (
                sesion.query(NovedadORM)
                .filter(NovedadORM.estado == EstadoNovedad.PENDIENTE.value)
                .all()
            )
            return [_a_dominio(fila) for fila in filas]
