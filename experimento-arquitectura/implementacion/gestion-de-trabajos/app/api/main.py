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
README.md."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI, HTTPException

from app.application.commands.crear_trabajo import CrearTrabajo
from app.application.queries.consultar_trabajo import ConsultarTrabajo
from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.schemas import TrabajoCreate, TrabajoIdOut, TrabajoOut
from app.domain.trabajo.trabajo import Trabajo
from app.infrastructure.messaging.publicador_pulsar import PublicadorPulsar
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
