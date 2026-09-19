"""API del microservicio Pagos — extraído de `gestion-de-trabajos` (donde
vivía como submódulo ACL) a su propio proceso/BD/despliegue.

Las rutas nunca tocan `SessionLocal`/`*ORM` directo, ni el agregado
directo — solo llaman a `application/commands` y `application/queries`
(Regla 5, criterio 2: arquitectura hexagonal). La única traducción
dominio -> HTTP ocurre aquí, en la función `_pago_a_schema`.

`POST /pagos` puebla `IRegistroTrabajosRepository` explícitamente antes de
ejecutar `PagarTrabajo` — ver README.md, sección "Frontera del API", para
la justificación completa de este cableado (reemplaza al dispatcher
intra-proceso que existía cuando Pagos compartía servicio con Gestión de
Trabajos)."""

from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import FastAPI, HTTPException, Request

from app.application.commands.compensar import Compensar, PagoNoEncontrado
from app.application.commands.pagar_trabajo import PagarTrabajo, TrabajoNoEncontrado
from app.application.ports.registro_trabajos import RegistroTrabajoElegible
from app.application.queries.consultar_pago import ConsultarPago
from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, establecer_trace, log_evento
from app.common.schemas import PagoCreate, PagoIdOut, PagoOut
from app.domain.pagos.pago import Pago
from app.domain.pagos.regla_regional import ReglaRegional
from app.domain.pagos.value_objects import ProveedorId, Region, TrabajoId
from app.infrastructure.adapters.pasarela_mercadopago import PasarelaMercadoPago
from app.infrastructure.adapters.pasarela_stripe import PasarelaStripe
from app.infrastructure.adapters.regla_brasil import ReglaBrasil
from app.infrastructure.adapters.regla_colombia import ReglaColombia
from app.infrastructure.persistence.pago_repository_sqlalchemy import (
    PagoRepositorySQLAlchemy,
)
from app.infrastructure.persistence.registro_trabajos_repository_sqlalchemy import (
    RegistroTrabajosRepositorySQLAlchemy,
)

logger = configurar_logging("api.main")
app = FastAPI(title="Pagos — API (Entrega 4 PoC, microservicio independiente)")


@app.middleware("http")
async def _telemetria_http(request: Request, call_next):
    establecer_trace(request.headers.get("x-cloud-trace-context"))
    inicio = time.perf_counter()
    status = 500
    try:
        respuesta = await call_next(request)
        status = respuesta.status_code
        return respuesta
    finally:
        if request.url.path != "/salud":
            ruta = getattr(request.scope.get("route"), "path", request.url.path)
            log_evento(
                logger,
                "http_request_completada",
                detalle=True,
                metodo=request.method,
                ruta=ruta,
                status=status,
                duracion_ms=round((time.perf_counter() - inicio) * 1000, 1),
            )


_pago_repo = PagoRepositorySQLAlchemy()
_registro_repo = RegistroTrabajosRepositorySQLAlchemy()

_reglas_regionales: dict[Region, ReglaRegional] = {
    Region.COLOMBIA: ReglaColombia(),
    Region.BRASIL: ReglaBrasil(),
}
_pasarelas = {
    "stripe": PasarelaStripe(),
    "mercadopago": PasarelaMercadoPago(),
}


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
    log_evento(
        logger,
        "api_iniciada",
        reglas_regionales=sorted(r.value for r in _reglas_regionales),
        pasarelas=sorted(_pasarelas),
    )


@app.get("/salud")
async def salud():
    return {"estado": "ok"}


@app.post("/pagos", response_model=PagoIdOut, status_code=201)
async def crear_pago(payload: PagoCreate):
    # Puebla el registro propio de este servicio ANTES de ejecutar el
    # comando — reemplaza al dispatcher intra-proceso que poblaba esto al
    # reaccionar a TrabajoFinalizado cuando Pagos vivía en el mismo proceso
    # que Gestión de Trabajos (ver README.md, "Frontera del API").
    log_evento(
        logger,
        "comando_pagar_trabajo_recibido",
        detalle=True,
        comando="PagarTrabajo",
        trabajo_id=str(payload.trabajo_id),
        region=payload.region,
        moneda=payload.moneda,
        monto=str(payload.monto),
        pasarela_solicitada=payload.pasarela,
    )
    await asyncio.to_thread(
        _registro_repo.guardar,
        RegistroTrabajoElegible(
            trabajo_id=TrabajoId(payload.trabajo_id),
            proveedor_id=ProveedorId(payload.proveedor_id),
            monto=payload.monto,
            moneda=payload.moneda,
            region=Region(payload.region),
        ),
    )

    comando = PagarTrabajo(_pago_repo, _registro_repo, _reglas_regionales, _pasarelas)
    try:
        pago_id = await comando.ejecutar(str(payload.trabajo_id), payload.pasarela)
    except TrabajoNoEncontrado as exc:
        raise HTTPException(status_code=404, detail="trabajo no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    log_evento(
        logger,
        "pago_creado",
        pago_id=str(pago_id),
        trabajo_id=str(payload.trabajo_id),
        agregado="Pago",
    )
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
