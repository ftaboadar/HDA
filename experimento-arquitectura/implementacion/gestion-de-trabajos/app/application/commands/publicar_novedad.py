"""Comando `PublicarNovedad` — reemplaza el cuerpo de `POST /novedades`; la
ruta HTTP nunca toca el ORM ni el agregado directo, ni el `ThrottlerCrm`
directo salvo a través de este comando (ver `app/api/main.py`).

CQS: `ejecutar()` retorna solo el `id` de la `Novedad` creada, nunca su
estado de negocio — igual que `CrearTrabajo` (ver ese docstring).

DISP-02 (ver `escenarios_calidad.md`): este comando NO llama al CRM ni
espera su respuesta — crea la `Novedad` (estado PENDIENTE), la persiste, y
la encola en el `ThrottlerCrm` con un `await queue.put(...)` que no bloquea
más allá del backpressure intencional de la cola (ver
`infrastructure/messaging/throttler.py`). Esto es lo que le permite a
`POST /novedades` responder `202 Accepted` de inmediato, sin que la
disponibilidad de Gestión de Trabajos dependa del estado del CRM."""

from __future__ import annotations

import asyncio
import uuid

from app.domain.novedades.fabrica import FabricaNovedad
from app.domain.novedades.repository import INovedadRepository
from app.domain.trabajo.value_objects import TrabajoId
from app.infrastructure.messaging.throttler import ThrottlerCrm


class PublicarNovedad:
    def __init__(self, repo: INovedadRepository, throttler: ThrottlerCrm) -> None:
        self._repo = repo
        self._throttler = throttler

    async def ejecutar(self, trabajo_id: str, descripcion: str) -> uuid.UUID:
        novedad = FabricaNovedad.crear(
            trabajo_id=TrabajoId.desde_str(trabajo_id),
            descripcion=descripcion,
        )

        # asyncio.to_thread: mismo hallazgo que en `crear_trabajo.py` — el
        # repositorio SQLAlchemy es síncrono, no debe bloquear el event loop.
        await asyncio.to_thread(self._repo.guardar, novedad)

        await self._throttler.encolar(novedad)

        return novedad.id
