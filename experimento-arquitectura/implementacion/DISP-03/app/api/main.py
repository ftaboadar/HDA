"""API de Verificación (ver plan.md, sección 5.1).

`POST /verificaciones` acepta y encola de inmediato — nunca espera al sistema
externo. Esa respuesta 202 inmediata es, en sí misma, la primera evidencia de
desacople que exige DISP-03.

Las rutas ya no tocan `SessionLocal`/`VerificacionORM` directo (esa era la
violación de hexagonal que la Regla 5, criterio 2, exige cerrar) — llaman a
`application/commands` y `application/queries`, que a su vez dependen del
puerto `IVerificacionRepository`, implementado por
`infrastructure/persistence/verificacion_repository_sqlalchemy.py`."""

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from app.application.commands.iniciar_verificacion import IniciarVerificacion
from app.application.commands.reprocesar_desde_dlq import ReprocesarDesdeDLQ
from app.application.commands.reprocesar_desde_dlq import VerificacionNoEncontrada as _NoEncDLQ
from app.application.commands.revalidar_proveedor import RevalidarProveedor
from app.application.queries.consultar_verificacion import ConsultarVerificacion
from app.application.queries.listar_dlq import ListarDLQ
from app.application.queries.listar_verificaciones import ListarVerificaciones
from app.common.config import settings
from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.mq import conectar, declarar_topologia
from app.common.publicador import Publicador, PublicadorPubSub, PublicadorRabbitMQ
from app.common.schemas import VerificacionCreate, VerificacionOut
from app.domain.verificacion.value_objects import MotivoRevalidacion
from app.domain.verificacion.verificacion import Verificacion
from app.infrastructure.persistence.verificacion_repository_sqlalchemy import (
    VerificacionRepositorySQLAlchemy,
)

logger = configurar_logging("api.main")
app = FastAPI(title="Verificación de Proveedores — API (DISP-03 PoC)")

_conexion = None
_publicador: Publicador | None = None
_repo = VerificacionRepositorySQLAlchemy()


def _a_schema(v: Verificacion) -> VerificacionOut:
    """Único punto de traducción dominio → contrato HTTP. El dominio no
    conoce Pydantic ni el contrato de transporte; esta función vive en la
    capa de infraestructura de entrada (api/), no en application/ ni en
    domain/."""
    ultimo = v.ultimo_intento
    return VerificacionOut(
        id=v.id,
        proveedor_id=str(v.proveedor_id),
        tipo_verificador=v.tipo_verificador.value,
        estado=v.estado.value,
        intentos=len(v.intentos),
        motivo_falla=(ultimo.error if v.estado.value == "FALLIDA_DLQ" and ultimo else None),
        creado_en=v.creado_en,
        actualizado_en=v.actualizado_en,
        completado_en=v.completado_en,
        en_dlq_desde=v.en_dlq_desde,
        reprocesos=v.reprocesos,
    )


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


@app.post("/verificaciones", response_model=VerificacionOut, status_code=202)
async def crear_verificacion(payload: VerificacionCreate):
    inicio = datetime.now(timezone.utc)
    assert _publicador is not None

    comando = IniciarVerificacion(_repo, _publicador)
    verificacion = await comando.ejecutar(payload.proveedor_id, payload.tipo_verificador)

    log_evento(
        logger,
        "verificacion_aceptada",
        verificacion_id=str(verificacion.id),
        tipo_verificador=payload.tipo_verificador,
        latencia_aceptacion_ms=int((datetime.now(timezone.utc) - inicio).total_seconds() * 1000),
    )
    return _a_schema(verificacion)


@app.get("/verificaciones/{verificacion_id}", response_model=VerificacionOut)
async def obtener_verificacion(verificacion_id: uuid.UUID):
    query = ConsultarVerificacion(_repo)
    verificacion = query.ejecutar(str(verificacion_id))
    if verificacion is None:
        raise HTTPException(status_code=404, detail="no encontrada")
    return _a_schema(verificacion)


@app.get("/verificaciones", response_model=list[VerificacionOut])
async def listar_verificaciones(estado: str | None = None, proveedor_id: str | None = None):
    query = ListarVerificaciones(_repo)
    return [_a_schema(v) for v in query.ejecutar(estado=estado, proveedor_id=proveedor_id)]


@app.get("/dlq", response_model=list[VerificacionOut])
async def listar_dlq():
    query = ListarDLQ(_repo)
    return [_a_schema(v) for v in query.ejecutar()]


@app.post("/dlq/{verificacion_id}/reprocesar", response_model=VerificacionOut)
async def reprocesar_dlq(verificacion_id: uuid.UUID):
    assert _publicador is not None
    comando = ReprocesarDesdeDLQ(_repo, _publicador)
    try:
        verificacion = await comando.ejecutar(str(verificacion_id))
    except _NoEncDLQ as exc:
        raise HTTPException(status_code=404, detail="no encontrada") from exc
    except Exception as exc:  # noqa: BLE001 — invariante de dominio violado (no está en DLQ)
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    log_evento(logger, "verificacion_reencolada_desde_dlq", verificacion_id=str(verificacion_id))
    return _a_schema(verificacion)


@app.post("/proveedores/{proveedor_id}/revalidar", response_model=VerificacionOut, status_code=202)
async def revalidar_proveedor(
    proveedor_id: str, tipo_verificador: str = "certificadora", motivo: str = "PROGRAMADA"
):
    """Endpoint manual del comando `RevalidarProveedor` (ver docstring del
    comando: el disparo automático por vencimiento o por alta de técnico
    nuevo no se implementa en este PoC)."""
    assert _publicador is not None
    comando = RevalidarProveedor(_repo, _publicador)
    verificacion = await comando.ejecutar(
        proveedor_id=proveedor_id,
        motivo=MotivoRevalidacion(motivo),
        tipo_verificador=tipo_verificador,
    )
    log_evento(logger, "proveedor_revalidacion_iniciada", proveedor_id=proveedor_id, motivo=motivo)
    return _a_schema(verificacion)
