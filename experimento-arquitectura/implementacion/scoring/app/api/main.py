"""Entrypoint HTTP del servicio Scoring (`uvicorn app.api.main:app`, ver
infra/service.tf). Expone el comando de actualización de score y la consulta
de un score existente — separados explícitamente (CQS, Regla 5 criterio 5):
`POST /scoring/actualizar` muta estado, `GET /scoring/{proveedor_id}` solo
lee.

Nota de alcance: el consumidor real de Pulsar (`TrabajoFinalizado` ->
actualizar score -> publicar `ScoringActualizado`) vive en
`app/worker/main.py` y hoy solo loguea el evento de dominio
`ScoringActualizadoEvent` (no lo publica todavía como evento de integración
a Pulsar, y ese worker tampoco tiene recurso de Cloud Run en infra/, ver el
comentario en infra/service.tf). El endpoint de comando de esta API permite
disparar una actualización manual equivalente por HTTP para pruebas/Postman
mientras esa parte del pipeline de eventos de integración no está completa.
"""

import logging
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.application.commands import ActualizarScoringCommand
from app.application.handlers import ActualizarScoringHandler
from app.domain.events import EventDispatcher, ScoringActualizadoEvent
from app.infrastructure.database import Base, engine
from app.infrastructure.repositories import SQLiteScoringRepository

logger = logging.getLogger(__name__)

app = FastAPI(title="Scoring API")


@app.on_event("startup")
def startup() -> None:
    # Se crea el esquema al arrancar (no al importar el módulo), para que
    # uvicorn pueda bindear el puerto y /salud responda aunque la conexión a
    # la base de datos tarde en estar lista (mismo patrón que
    # gestion-de-trabajos/app/api/main.py).
    Base.metadata.create_all(engine)


@app.get("/salud")
def salud():
    return {"status": "ok", "servicio": "scoring"}


def _dispatcher() -> EventDispatcher:
    dispatcher = EventDispatcher()

    def _on_scoring_actualizado(event: ScoringActualizadoEvent) -> None:
        # Evento de DOMINIO intra-servicio (no cruza a Pulsar desde aquí).
        logger.info(
            "[INTRA-EVENT] Scoring actualizado para %s: %s",
            event.fotografo_id,
            event.nueva_puntuacion,
        )

    dispatcher.subscribe(type(ScoringActualizadoEvent), _on_scoring_actualizado)
    return dispatcher


class ActualizarScoringRequest(BaseModel):
    proveedor_id: UUID
    calificacion: float


class ScoringResponse(BaseModel):
    proveedor_id: UUID
    puntuacion_actual: float
    trabajos_completados: int


@app.post("/scoring/actualizar", response_model=ScoringResponse, status_code=200)
def actualizar_scoring(req: ActualizarScoringRequest):
    repository = SQLiteScoringRepository()
    handler = ActualizarScoringHandler(repository, _dispatcher())
    comando = ActualizarScoringCommand(
        fotografo_id=req.proveedor_id, calificacion=req.calificacion
    )
    handler.handle(comando)

    actualizado = repository.get_by_fotografo_id(req.proveedor_id)
    return ScoringResponse(
        proveedor_id=actualizado.fotografo_id,
        puntuacion_actual=actualizado.puntuacion_actual,
        trabajos_completados=actualizado.trabajos_completados,
    )


@app.get("/scoring/{proveedor_id}", response_model=ScoringResponse)
def obtener_scoring(proveedor_id: UUID):
    repository = SQLiteScoringRepository()
    scoring = repository.get_by_fotografo_id(proveedor_id)
    if not scoring:
        raise HTTPException(status_code=404, detail="Score no encontrado")
    return ScoringResponse(
        proveedor_id=scoring.fotografo_id,
        puntuacion_actual=scoring.puntuacion_actual,
        trabajos_completados=scoring.trabajos_completados,
    )
