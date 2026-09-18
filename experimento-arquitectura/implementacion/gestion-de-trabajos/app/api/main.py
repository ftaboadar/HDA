"""API de Gestión de Trabajos.

Las rutas nunca tocan `SessionLocal`/`*ORM` directo, ni el agregado
directo — solo llaman a `application/commands` y `application/queries`
(Regla 5, criterio 2: arquitectura hexagonal). La única traducción
dominio -> HTTP ocurre aquí, en `_trabajo_a_schema`.

`POST /trabajos` es la puerta de entrada HTTP del propio servicio -- no una
llamada síncrona de un microservicio a otro (esa sigue prohibida por
12-plan-entrega-4.md sección 3.1); la comunicación real hacia
Proveedores/Reputación es 100% por el tópico `trabajos.finalizado` en
Pulsar, publicado dentro de `CrearTrabajo`.

Nota (separación de Pagos): las rutas `POST /pagos`, `GET /pagos/{id}` y
`POST /pagos/{id}/compensar` que antes vivían aquí como submódulo ACL se
movieron al microservicio independiente `implementacion/pagos/` — ver su
README.md.

DISP-02 (Sidecar/Throttler hacia el CRM "Gestión de Agentes", ver
`escenarios_calidad.md`): `POST /novedades` responde `202 Accepted` de
inmediato — no espera la entrega real al CRM externo (eso lo hace, en
background, `ThrottlerCrm`, arrancado en `startup` y cancelado limpio en
`shutdown`)."""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException

from app.application.commands.crear_trabajo import CrearTrabajo
from app.application.commands.publicar_novedad import PublicarNovedad
from app.application.queries.consultar_novedad import ConsultarNovedad
from app.application.queries.consultar_trabajo import ConsultarTrabajo
from app.common.config import settings
from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.schemas import (
    NovedadCreate,
    NovedadIdOut,
    NovedadOut,
    TrabajoCreate,
    TrabajoIdOut,
    TrabajoOut,
)
from app.domain.trabajo.trabajo import Trabajo
from app.infrastructure.adapters.throttler_crm import AdaptadorGestionAgentesHttp
from app.infrastructure.messaging.publicador_pulsar import PublicadorPulsar
from app.infrastructure.messaging.throttler import ThrottlerCrm
from app.infrastructure.persistence.novedad_repository_sqlalchemy import (
    NovedadRepositorySQLAlchemy,
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
_registro_repo = RegistroTrabajosRepositorySQLAlchemy()
_publicador = PublicadorPulsar()

_novedad_repo = NovedadRepositorySQLAlchemy()
_crm_puerto = AdaptadorGestionAgentesHttp()
_throttler = ThrottlerCrm(puerto_crm=_crm_puerto, repo=_novedad_repo)


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


@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    # Sube el executor por defecto de asyncio (default: min(32, cpu+4)
    # threads) a un tamaño DERIVADO de `settings.db_pool_size +
    # settings.db_max_overflow` -- ya NO un literal aparte (era 100 fijo,
    # desincronizado del pool real y de `max_instance_request_concurrency`
    # de Cloud Run, causa raíz de que subir la concurrencia de Cloud Run a
    # 200 sin tocar este número solo moviera la cola adentro de la
    # instancia — ver comentario junto a `sql_tier` en
    # infra/variables.tf para el cálculo completo de capacidad). Cada
    # `asyncio.to_thread(...)` (guardar Trabajo, guardar RegistroTrabajo,
    # y el `run_in_executor` de PublicadorPulsar — las tres comparten
    # este mismo executor) necesita un hilo propio; con menos hilos que
    # `containerConcurrency`, las requests entrantes hacen cola DENTRO de
    # la instancia antes de tocar la base de datos o Pulsar.
    asyncio.get_event_loop().set_default_executor(
        ThreadPoolExecutor(max_workers=settings.db_pool_size + settings.db_max_overflow)
    )
    _throttler.iniciar()
    log_evento(logger, "api_iniciada")


@app.on_event("shutdown")
async def shutdown() -> None:
    await _throttler.detener()
    log_evento(logger, "api_detenida")


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


@app.post("/novedades", response_model=NovedadIdOut, status_code=202)
async def publicar_novedad(payload: NovedadCreate):
    """202 Accepted, no 201 Created: la `Novedad` ya quedó persistida como
    PENDIENTE y encolada en el Throttler, pero su entrega real al CRM
    "Gestión de Agentes" es asíncrona (DISP-02) — el código de estado deja
    explícito que la petición fue aceptada para proceso, no completada."""
    comando = PublicarNovedad(_novedad_repo, _throttler)
    novedad_id = await comando.ejecutar(payload.trabajo_id, payload.descripcion)
    log_evento(logger, "novedad_publicada", novedad_id=str(novedad_id))
    return NovedadIdOut(id=novedad_id)


@app.get("/novedades/{novedad_id}", response_model=NovedadOut)
async def obtener_novedad(novedad_id: uuid.UUID):
    """Agregado en esta tarea (DISP-02) — ver docstring de
    `application/queries/consultar_novedad.py`."""
    query = ConsultarNovedad(_novedad_repo)
    novedad = await asyncio.to_thread(query.ejecutar, str(novedad_id))
    if novedad is None:
        raise HTTPException(status_code=404, detail="no encontrada")
    return NovedadOut(
        id=novedad.id,
        trabajo_id=novedad.trabajo_id.valor,
        descripcion=novedad.descripcion,
        estado=novedad.estado.value,
        intentos=novedad.intentos,
        creado_en=novedad.creado_en,
    )
