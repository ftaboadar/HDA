"""API de Verificación (ver plan.md, sección 5.1).

`POST /verificaciones` acepta y encola de inmediato — nunca espera al sistema
externo. Esa respuesta 202 inmediata es, en sí misma, la primera evidencia de
desacople que exige DISP-03."""

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from sqlalchemy import select

from app.common.config import settings
from app.common.db import Base, SessionLocal, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.models_db import VerificacionORM
from app.common.mq import conectar, declarar_topologia
from app.common.publicador import Publicador, PublicadorPubSub, PublicadorRabbitMQ
from app.common.schemas import VerificacionCreate, VerificacionOut

logger = configurar_logging("api.main")
app = FastAPI(title="Verificación de Proveedores — API (DISP-03 PoC)")

_conexion = None
_publicador: Publicador | None = None


@app.on_event("startup")
async def startup() -> None:
    global _conexion, _publicador
    Base.metadata.create_all(bind=engine)

    if settings.transporte == "pubsub":
        _publicador = PublicadorPubSub(
            project_id=settings.gcp_project,
            topic_solicitudes=settings.pubsub_topic_solicitudes,
            topic_fallidas=settings.pubsub_topic_fallidas,
        )
    else:
        _conexion = await conectar()
        canal = await _conexion.channel()
        exchange_sol, exchange_dlx, _, _ = await declarar_topologia(canal)
        _publicador = PublicadorRabbitMQ(exchange_sol, exchange_dlx)

    log_evento(logger, "api_iniciada", transporte=settings.transporte)


@app.on_event("shutdown")
async def shutdown() -> None:
    if _conexion:
        await _conexion.close()


@app.get("/salud")
async def salud():
    return {"estado": "ok"}


def _consultar(estado: str | None = None, proveedor_id: str | None = None):
    with SessionLocal() as sesion:
        consulta = select(VerificacionORM)
        if estado:
            consulta = consulta.where(VerificacionORM.estado == estado)
        if proveedor_id:
            consulta = consulta.where(VerificacionORM.proveedor_id == proveedor_id)
        filas = sesion.execute(consulta).scalars().all()
        return [VerificacionOut.model_validate(f) for f in filas]


@app.post("/verificaciones", response_model=VerificacionOut, status_code=202)
async def crear_verificacion(payload: VerificacionCreate):
    inicio = datetime.now(timezone.utc)
    verificacion_id = uuid.uuid4()

    with SessionLocal() as sesion:
        fila = VerificacionORM(
            id=verificacion_id,
            proveedor_id=payload.proveedor_id,
            tipo_verificador=payload.tipo_verificador,
            estado="PENDIENTE",
        )
        sesion.add(fila)
        sesion.commit()
        sesion.refresh(fila)
        resultado = VerificacionOut.model_validate(fila)

    assert _publicador is not None
    await _publicador.publicar_solicitud(
        {
            "verificacion_id": str(verificacion_id),
            "proveedor_id": payload.proveedor_id,
            "tipo_verificador": payload.tipo_verificador,
            "solicitado_en": inicio.isoformat(),
        }
    )

    log_evento(
        logger,
        "verificacion_aceptada",
        verificacion_id=str(verificacion_id),
        tipo_verificador=payload.tipo_verificador,
        latencia_aceptacion_ms=int((datetime.now(timezone.utc) - inicio).total_seconds() * 1000),
    )
    return resultado


@app.get("/verificaciones/{verificacion_id}", response_model=VerificacionOut)
async def obtener_verificacion(verificacion_id: uuid.UUID):
    with SessionLocal() as sesion:
        fila = sesion.get(VerificacionORM, verificacion_id)
        if fila is None:
            raise HTTPException(status_code=404, detail="no encontrada")
        return VerificacionOut.model_validate(fila)


@app.get("/verificaciones", response_model=list[VerificacionOut])
async def listar_verificaciones(estado: str | None = None, proveedor_id: str | None = None):
    return _consultar(estado=estado, proveedor_id=proveedor_id)


@app.get("/dlq", response_model=list[VerificacionOut])
async def listar_dlq():
    return _consultar(estado="FALLIDA_DLQ")


@app.post("/dlq/{verificacion_id}/reprocesar", response_model=VerificacionOut)
async def reprocesar_dlq(verificacion_id: uuid.UUID):
    with SessionLocal() as sesion:
        fila = sesion.get(VerificacionORM, verificacion_id)
        if fila is None:
            raise HTTPException(status_code=404, detail="no encontrada")
        if fila.estado != "FALLIDA_DLQ":
            raise HTTPException(status_code=409, detail="la verificación no está en DLQ")
        fila.estado = "PENDIENTE"
        fila.intentos = 0
        fila.reprocesos += 1
        fila.motivo_falla = None
        sesion.commit()
        sesion.refresh(fila)
        resultado = VerificacionOut.model_validate(fila)

    assert _publicador is not None
    await _publicador.publicar_solicitud(
        {
            "verificacion_id": str(verificacion_id),
            "proveedor_id": resultado.proveedor_id,
            "tipo_verificador": resultado.tipo_verificador,
            "solicitado_en": datetime.now(timezone.utc).isoformat(),
            "reprocesado": True,
        }
    )
    log_evento(logger, "verificacion_reencolada_desde_dlq", verificacion_id=str(verificacion_id))
    return resultado
