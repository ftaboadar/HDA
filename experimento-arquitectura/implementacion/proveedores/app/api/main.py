"""Adaptador de entrada HTTP (FastAPI) — arquitectura hexagonal, Regla 5
criterio 2: esta capa solo traduce HTTP <-> casos de uso de
`app/verificacion/application/` (commands mutan, queries solo leen — CQS,
criterio 5). Nunca importa SQLAlchemy ni construye `Verificacion` a mano;
eso vive en `app/verificacion/domain/` e
`app/verificacion/infrastructure/persistence/`.

Antes de este cambio, este archivo era un stub sin `/salud` ni rutas reales
(`POST /webhooks/certificadora` de juguete) mientras el dominio/aplicación de
Verificación (DISP-03) ya estaba completo pero nunca se conectó a HTTP — ver
`experimento-arquitectura/implementacion/ESTADO-IMPLEMENTACION.md`.

Contrato HTTP tomado de `tests/test_escenarios_disp03.py` (CP-1..CP-7, ver
`tests/conftest.py:crear_verificacion/esperar_estado`), que ya asumía este
contrato contra un stack real:
  POST /verificaciones            {proveedor_id, tipo_verificador} -> 201
  GET  /verificaciones/{id}       -> 200 | 404
  GET  /verificaciones            -> 200 (filtros opcionales ?estado=&proveedor_id=)
  GET  /dlq                       -> 200 (lista de FALLIDA_DLQ)
  POST /dlq/{id}/reprocesar       -> 200 | 404 | 409 (invariante de reproceso)

Fuera de alcance de este cambio (ver docstring de `RegistrarIntento`): no hay
`POST /verificaciones/{id}/intentos` — ese comando lo invoca el WORKER como
reacción a la respuesta del verificador externo, nunca un cliente HTTP
directo. Tampoco se conecta aquí `RevalidarProveedor` (comando aún stub —
`ejecutar()` es un `pass` literal en
`app/verificacion/application/commands/revalidar_proveedor.py`, y su firma
no coincide con la que ya lo invocan `app/worker/main.py` /
`app/verificacion/infrastructure/messaging/consumidor_pulsar.py`, que le
pasan un `motivo=` que el método no acepta): exponerlo por HTTP sin lógica
real sería fingir una funcionalidad que no existe. Documentado también en
ESTADO-IMPLEMENTACION.md para que quede trazado, no perdido."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.common.config import settings
from app.common.db import Base, engine
from app.common.publicador import Publicador, PublicadorPubSub, PublicadorPulsar, PublicadorRabbitMQ
from app.common.schemas import VerificacionCreate, VerificacionOut
from app.verificacion.application.commands.iniciar_verificacion import IniciarVerificacion
from app.verificacion.application.commands.reprocesar_desde_dlq import (
    ReprocesarDesdeDLQ,
    VerificacionNoEncontrada,
)
from app.verificacion.application.queries.consultar_verificacion import ConsultarVerificacion
from app.verificacion.application.queries.listar_dlq import ListarDLQ
from app.verificacion.application.queries.listar_verificaciones import ListarVerificaciones
from app.verificacion.domain.value_objects import EstadoVerificacion
from app.verificacion.domain.verificacion import ErrorTransicionInvalida, Verificacion
from app.verificacion.infrastructure.persistence.verificacion_repository_sqlalchemy import (
    VerificacionRepositorySQLAlchemy,
)

logger = logging.getLogger("api.main")

repo = VerificacionRepositorySQLAlchemy()

# Estado del adaptador de mensajería saliente (puerto `Publicador`, ver
# app/common/publicador.py) — se resuelve en el lifespan porque el
# transporte "rabbitmq" necesita abrir una conexión async y declarar su
# topología antes de poder publicar (los otros dos transportes se
# construyen de forma síncrona, pero se resuelven aquí también para que
# exista un único punto de composición).
_estado: dict[str, object] = {"publicador": None, "conexion_rabbitmq": None}


async def _crear_publicador() -> Publicador:
    if settings.transporte == "rabbitmq":
        from app.common.mq import conectar, declarar_topologia

        conexion = await conectar()
        canal = await conexion.channel()
        exchange_sol, exchange_dlx, _cola_sol, _cola_dlq = await declarar_topologia(canal)
        _estado["conexion_rabbitmq"] = conexion
        return PublicadorRabbitMQ(exchange_solicitudes=exchange_sol, exchange_dlx=exchange_dlx)

    if settings.transporte == "pubsub":
        return PublicadorPubSub(
            project_id=settings.gcp_project,
            topic_solicitudes=settings.pubsub_topic_solicitudes,
            topic_fallidas=settings.pubsub_topic_fallidas,
            topic_eventos=settings.pubsub_topic_eventos,
        )

    if settings.transporte == "pulsar":
        return PublicadorPulsar(
            service_url=settings.pulsar_service_url,
            topic_solicitudes=settings.pulsar_topic_solicitudes,
            topic_fallidas=settings.pulsar_topic_fallidas,
            topic_eventos=settings.pulsar_topic_eventos,
        )

    raise RuntimeError(f"TRANSPORTE desconocido: {settings.transporte!r}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Sin Alembic en este PoC (ver docstring de app/common/models_db.py):
    # create_all crea las tablas si no existen, es idempotente.
    Base.metadata.create_all(bind=engine)
    _estado["publicador"] = await _crear_publicador()
    logger.info("proveedores-api iniciada (transporte=%s)", settings.transporte)
    try:
        yield
    finally:
        conexion = _estado.get("conexion_rabbitmq")
        if conexion is not None:
            await conexion.close()


app = FastAPI(title="Proveedores API", lifespan=lifespan)


def _publicador() -> Publicador:
    publicador = _estado["publicador"]
    if publicador is None:  # pragma: no cover - solo si se llama fuera del lifespan (tests)
        raise RuntimeError("Publicador no inicializado — ¿lifespan no corrió?")
    return publicador  # type: ignore[return-value]


def _a_out(v: Verificacion) -> VerificacionOut:
    """Mapper dominio -> DTO HTTP. Vive en el adaptador de entrada, no en el
    dominio (Regla 5, criterio 2): `Verificacion.intentos` es una lista de
    `IntentoVerificacion` (trazabilidad completa), pero el contrato HTTP
    heredado (`VerificacionOut`, ver docstring de models_db.py: "el contrato
    HTTP no cambia") expone un conteo (`intentos: int`) y el motivo de la
    falla del ÚLTIMO intento — la misma proyección que ya hacía
    `VerificacionRepositorySQLAlchemy.guardar` sobre `VerificacionORM`."""
    ultimo = v.ultimo_intento
    motivo_falla = (
        ultimo.error if (v.estado == EstadoVerificacion.FALLIDA_DLQ and ultimo) else None
    )
    return VerificacionOut(
        id=v.id,
        proveedor_id=str(v.proveedor_id),
        tipo_verificador=v.tipo_verificador.value,
        estado=v.estado.value,
        intentos=len(v.intentos),
        motivo_falla=motivo_falla,
        creado_en=v.creado_en,
        actualizado_en=v.actualizado_en,
        completado_en=v.completado_en,
        en_dlq_desde=v.en_dlq_desde,
        reprocesos=v.reprocesos,
    )


@app.get("/salud")
def salud() -> dict:
    """Healthcheck de Cloud Run (CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §5) —
    deliberadamente sin tocar la BD ni el broker: si el proceso responde,
    está vivo; la disponibilidad de sus dependencias la miden CP-1..CP-7,
    no este endpoint."""
    return {"status": "ok", "service": "proveedores-api"}


@app.post("/verificaciones", response_model=VerificacionOut, status_code=201)
async def crear_verificacion(body: VerificacionCreate) -> VerificacionOut:
    """Comando — muta estado (crea el agregado). CQS: ver GET de abajo."""
    comando = IniciarVerificacion(repo, _publicador())
    verificacion = await comando.ejecutar(
        proveedor_id=body.proveedor_id, tipo_verificador=body.tipo_verificador
    )
    return _a_out(verificacion)


@app.get("/verificaciones/{verificacion_id}", response_model=VerificacionOut)
def obtener_verificacion(verificacion_id: str) -> VerificacionOut:
    """Query — solo lee (CQS)."""
    verificacion = ConsultarVerificacion(repo).ejecutar(verificacion_id)
    if verificacion is None:
        raise HTTPException(status_code=404, detail="verificación no encontrada")
    return _a_out(verificacion)


@app.get("/verificaciones", response_model=list[VerificacionOut])
def listar_verificaciones(
    estado: str | None = None, proveedor_id: str | None = None
) -> list[VerificacionOut]:
    """Query — solo lee (CQS)."""
    verificaciones = ListarVerificaciones(repo).ejecutar(estado=estado, proveedor_id=proveedor_id)
    return [_a_out(v) for v in verificaciones]


@app.get("/dlq", response_model=list[VerificacionOut])
def listar_dlq() -> list[VerificacionOut]:
    """Query — solo lee (CQS). Verificaciones en FALLIDA_DLQ, visibles para
    reproceso manual (CP-4/CP-6 de plan.md)."""
    return [_a_out(v) for v in ListarDLQ(repo).ejecutar()]


@app.post("/dlq/{verificacion_id}/reprocesar", response_model=VerificacionOut)
async def reprocesar_dlq(verificacion_id: str) -> VerificacionOut:
    """Comando — muta estado (FALLIDA_DLQ -> PENDIENTE, re-encola). CQS: ver
    GET /dlq de arriba, que es la única forma de leer este mismo dato."""
    comando = ReprocesarDesdeDLQ(repo, _publicador())
    try:
        verificacion = await comando.ejecutar(verificacion_id)
    except VerificacionNoEncontrada as exc:
        raise HTTPException(status_code=404, detail="verificación no encontrada") from exc
    except ErrorTransicionInvalida as exc:
        # Invariante del agregado (Verificacion.reprocesar): solo se puede
        # reprocesar desde FALLIDA_DLQ — 409, no 400: el request está bien
        # formado, es el ESTADO actual del recurso el que lo rechaza.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _a_out(verificacion)
