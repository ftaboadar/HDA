"""API de Gestión de Trabajos (+ módulo ACL de Pagos).

Las rutas nunca tocan `SessionLocal`/`*ORM` directo, ni el agregado
directo — solo llaman a `application/commands` y `application/queries`
(Regla 5, criterio 2: arquitectura hexagonal). La única traducción
dominio -> HTTP ocurre aquí, en las funciones `_trabajo_a_schema` /
`_pago_a_schema`.

`POST /trabajos` y `POST /pagos` son la puerta de entrada HTTP del propio
servicio -- no una llamada síncrona de un microservicio a otro (esa sigue
prohibida por 12-plan-entrega-4.md sección 3.1); la comunicación real hacia
Proveedores/Reputación es 100% por el tópico `trabajos.finalizado` en
Pulsar, publicado dentro de `CrearTrabajo`."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI, HTTPException

from app.application.commands.compensar import Compensar, PagoNoEncontrado
from app.application.commands.crear_trabajo import CrearTrabajo
from app.application.commands.pagar_trabajo import PagarTrabajo, TrabajoNoEncontrado
from app.application.queries.consultar_pago import ConsultarPago
from app.application.queries.consultar_trabajo import ConsultarTrabajo
from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.schemas import (
    PagoCreate,
    PagoIdOut,
    PagoOut,
    TrabajoCreate,
    TrabajoIdOut,
    TrabajoOut,
)
from app.domain.pagos.pago import Pago
from app.domain.pagos.regla_regional import ReglaRegional
from app.domain.trabajo.trabajo import Trabajo
from app.domain.trabajo.value_objects import Region
from app.infrastructure.adapters.pasarela_mercadopago import PasarelaMercadoPago
from app.infrastructure.adapters.pasarela_stripe import PasarelaStripe
from app.infrastructure.adapters.regla_brasil import ReglaBrasil
from app.infrastructure.adapters.regla_colombia import ReglaColombia
from app.infrastructure.messaging.publicador_pulsar import PublicadorPulsar
from app.infrastructure.persistence.pago_repository_sqlalchemy import (
    PagoRepositorySQLAlchemy,
)
from app.infrastructure.persistence.registro_trabajos_repository_sqlalchemy import (
    RegistroTrabajosRepositorySQLAlchemy,
)
from app.infrastructure.persistence.trabajo_repository_sqlalchemy import (
    TrabajoRepositorySQLAlchemy,
)

logger = configurar_logging("api.main")
app = FastAPI(title="Gestión de Trabajos — API (Entrega 4 PoC, skeleton)")

_trabajo_repo = TrabajoRepositorySQLAlchemy()
_pago_repo = PagoRepositorySQLAlchemy()
_registro_repo = RegistroTrabajosRepositorySQLAlchemy()
_publicador = PublicadorPulsar()

_reglas_regionales: dict[Region, ReglaRegional] = {
    Region.COLOMBIA: ReglaColombia(),
    Region.BRASIL: ReglaBrasil(),
}
_pasarelas = {
    "stripe": PasarelaStripe(),
    "mercadopago": PasarelaMercadoPago(),
}


def _trabajo_a_schema(t: Trabajo) -> TrabajoOut:
    return TrabajoOut(
        id=t.id,
        proveedor_id=str(t.proveedor_id),
        estado=t.estado.value,
        monto=t.monto.valor,
        moneda=t.monto.moneda,
        region=t.region.value,
        fecha_creacion=t.fecha_creacion,
    )


def _pago_a_schema(p: Pago) -> PagoOut:
    return PagoOut(
        id=p.id,
        trabajo_id=p.trabajo_id.valor,
        monto=p.monto.valor,
        moneda=p.monto.moneda,
        region=p.region.value,
        pasarela=p.pasarela.value,
        estado=p.estado.value,
        referencia_externa=p.referencia_externa,
        motivo_falla=p.motivo_falla,
    )


@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    log_evento(logger, "api_iniciada")


@app.get("/salud")
async def salud():
    return {"estado": "ok"}


@app.post("/trabajos", response_model=TrabajoIdOut, status_code=201)
async def crear_trabajo(payload: TrabajoCreate):
    comando = CrearTrabajo(_trabajo_repo, _publicador, _registro_repo)
    trabajo_id = await comando.ejecutar(
        payload.proveedor_id, payload.monto, payload.region
    )
    log_evento(logger, "trabajo_creado", trabajo_id=str(trabajo_id))
    return TrabajoIdOut(id=trabajo_id)


@app.get("/trabajos/{trabajo_id}", response_model=TrabajoOut)
async def obtener_trabajo(trabajo_id: uuid.UUID):
    query = ConsultarTrabajo(_trabajo_repo)
    # asyncio.to_thread: ejecutar() es SQLAlchemy síncrono — ver docstring
    # de application/commands/crear_trabajo.py para el hallazgo (k6 real
    # bloqueando el event loop).
    trabajo = await asyncio.to_thread(query.ejecutar, str(trabajo_id))
    if trabajo is None:
        raise HTTPException(status_code=404, detail="no encontrado")
    return _trabajo_a_schema(trabajo)


@app.post("/pagos", response_model=PagoIdOut, status_code=201)
async def crear_pago(payload: PagoCreate):
    comando = PagarTrabajo(_pago_repo, _registro_repo, _reglas_regionales, _pasarelas)
    try:
        pago_id = await comando.ejecutar(str(payload.trabajo_id), payload.pasarela)
    except TrabajoNoEncontrado as exc:
        raise HTTPException(status_code=404, detail="trabajo no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    log_evento(logger, "pago_creado", pago_id=str(pago_id))
    return PagoIdOut(id=pago_id)


@app.get("/pagos/{pago_id}", response_model=PagoOut)
async def obtener_pago(pago_id: uuid.UUID):
    query = ConsultarPago(_pago_repo)
    pago = await asyncio.to_thread(query.ejecutar, str(pago_id))
    if pago is None:
        raise HTTPException(status_code=404, detail="no encontrado")
    return _pago_a_schema(pago)


@app.post("/pagos/{pago_id}/compensar", response_model=PagoIdOut)
async def compensar_pago(pago_id: uuid.UUID):
    comando = Compensar(_pago_repo)
    try:
        id_compensado = await comando.ejecutar(str(pago_id))
    except PagoNoEncontrado as exc:
        raise HTTPException(status_code=404, detail="no encontrado") from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    log_evento(logger, "pago_compensado_via_api", pago_id=str(pago_id))
    return PagoIdOut(id=id_compensado)
