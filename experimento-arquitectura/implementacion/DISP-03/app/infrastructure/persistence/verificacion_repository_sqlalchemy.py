"""Adaptador concreto de `IVerificacionRepository` sobre SQLAlchemy/Postgres.

Es la única pieza del sistema que traduce entre el lenguaje del dominio
(`Verificacion`, `VerificacionId`, `ProveedorId`, VOs) y el de persistencia
(`VerificacionORM`, `IntentoVerificacionORM`) — ni `app/api/`, ni
`app/application/`, ni `app/domain/` conocen SQLAlchemy después de este
cambio; antes de él, `app/api/main.py` importaba `VerificacionORM` y
`SessionLocal` directo en los handlers (la violación de hexagonal que la
Regla 5, criterio 2, exige cerrar)."""

from datetime import datetime, timezone

from app.common.db import SessionLocal
from app.common.models_db import IntentoVerificacionORM, VerificacionORM
from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.value_objects import (
    EstadoVerificacion,
    ProveedorId,
    ResultadoIntento,
    TipoVerificador,
    VerificacionId,
)
from app.domain.verificacion.verificacion import IntentoVerificacion, Verificacion


def _a_dominio(fila: VerificacionORM) -> Verificacion:
    intentos = [
        IntentoVerificacion(
            id=i.id,
            numero=i.numero,
            resultado=ResultadoIntento(i.resultado),
            duracion_ms=i.duracion_ms,
            error=i.error,
            ocurrido_en=i.ocurrido_en,
        )
        for i in sorted(fila.intentos_registrados, key=lambda i: i.numero)
    ]
    return Verificacion(
        id=fila.id,
        proveedor_id=ProveedorId(fila.proveedor_id),
        tipo_verificador=TipoVerificador(fila.tipo_verificador),
        estado=EstadoVerificacion(fila.estado),
        intentos=intentos,
        reprocesos=fila.reprocesos,
        creado_en=fila.creado_en,
        actualizado_en=fila.actualizado_en,
        completado_en=fila.completado_en,
        en_dlq_desde=fila.en_dlq_desde,
    )


class VerificacionRepositorySQLAlchemy(IVerificacionRepository):
    def guardar(self, verificacion: Verificacion) -> None:
        with SessionLocal() as sesion:
            fila = sesion.get(VerificacionORM, verificacion.id)
            if fila is None:
                fila = VerificacionORM(id=verificacion.id)
                sesion.add(fila)

            fila.proveedor_id = str(verificacion.proveedor_id)
            fila.tipo_verificador = verificacion.tipo_verificador.value
            fila.estado = verificacion.estado.value
            fila.reprocesos = verificacion.reprocesos
            fila.intentos = len(verificacion.intentos)

            ultimo = verificacion.ultimo_intento
            if verificacion.estado == EstadoVerificacion.FALLIDA_DLQ:
                fila.motivo_falla = ultimo.error if ultimo else None
                if fila.en_dlq_desde is None:
                    fila.en_dlq_desde = datetime.now(timezone.utc)
            elif verificacion.estado == EstadoVerificacion.COMPLETADA:
                if fila.completado_en is None:
                    fila.completado_en = datetime.now(timezone.utc)
                fila.motivo_falla = None
            else:  # PENDIENTE (incluye reproceso: se limpia el rastro anterior)
                fila.motivo_falla = None
                fila.en_dlq_desde = None
                fila.completado_en = None

            # Los intentos se resincronizan completos — simple y correcto a
            # esta escala; una estrategia incremental (diff) no aporta nada
            # aquí porque el agregado siempre trae la lista completa.
            sesion.query(IntentoVerificacionORM).filter_by(verificacion_id=verificacion.id).delete()
            for intento in verificacion.intentos:
                sesion.add(
                    IntentoVerificacionORM(
                        id=intento.id,
                        verificacion_id=verificacion.id,
                        numero=intento.numero,
                        resultado=intento.resultado.value,
                        error=intento.error,
                        duracion_ms=intento.duracion_ms,
                        ocurrido_en=intento.ocurrido_en,
                    )
                )

            sesion.commit()

    def obtener_por_id(self, id: VerificacionId) -> Verificacion | None:
        with SessionLocal() as sesion:
            fila = sesion.get(VerificacionORM, id.valor)
            return _a_dominio(fila) if fila else None

    def listar_por_proveedor(self, proveedor_id: ProveedorId) -> list[Verificacion]:
        with SessionLocal() as sesion:
            filas = (
                sesion.query(VerificacionORM)
                .filter(VerificacionORM.proveedor_id == str(proveedor_id))
                .all()
            )
            return [_a_dominio(f) for f in filas]

    def listar_en_dlq(self) -> list[Verificacion]:
        return self.listar(estado=EstadoVerificacion.FALLIDA_DLQ.value)

    def listar(
        self, estado: str | None = None, proveedor_id: ProveedorId | None = None
    ) -> list[Verificacion]:
        with SessionLocal() as sesion:
            consulta = sesion.query(VerificacionORM)
            if estado:
                consulta = consulta.filter(VerificacionORM.estado == estado)
            if proveedor_id:
                consulta = consulta.filter(VerificacionORM.proveedor_id == str(proveedor_id))
            return [_a_dominio(f) for f in consulta.all()]
