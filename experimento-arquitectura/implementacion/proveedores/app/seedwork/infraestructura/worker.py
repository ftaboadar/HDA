"""Worker estándar (CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §5) — copiado
(no importado, ver docstring de app/common/logging_utils.py: cada servicio es
su propio Bounded Context) del mismo patrón ya usado por
`gestion-de-trabajos` y `marketplace`.

Cloud Run exige un puerto HTTP, y un consumidor Pulsar es un bucle de pull sin
HTTP (por eso el consumidor de Reputación nunca se desplegó en la Entrega 4).
`crear_app_worker` arranca todos los consumidores del servicio en hilos y
expone `GET /salud`, que responde 200 solo si todos siguen vivos (503 si
alguno murió, para que Cloud Run reinicie la instancia).

Uso en `app/worker/main.py`:

    app = crear_app_worker(lambda: [ConsumidorSolicitudes(), ConsumidorTrabajosFinalizado()])

y se corre con `uvicorn app.worker.main:app --port 8080` (o
`python -m app.worker.main`). La fábrica se llama en el startup, no al
importar, para que importar el módulo no conecte a Pulsar."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Protocol

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.common.logging_utils import configurar_logging, log_evento

logger = configurar_logging("worker.main")


class Consumidor(Protocol):
    suscripcion: str

    def iniciar_en_hilo(self) -> None: ...

    def vivo(self) -> bool: ...

    def detener(self) -> None: ...


def crear_app_worker(
    fabrica_consumidores: Callable[[], list[Consumidor]],
    al_iniciar: Callable[[], None] | None = None,
) -> FastAPI:
    consumidores: list[Consumidor] = []

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        if al_iniciar is not None:
            al_iniciar()
        consumidores.extend(fabrica_consumidores())
        for consumidor in consumidores:
            consumidor.iniciar_en_hilo()
        log_evento(
            logger,
            "worker_iniciado",
            suscripciones=[c.suscripcion for c in consumidores],
        )
        yield
        for consumidor in consumidores:
            consumidor.detener()

    app = FastAPI(title="Worker de consumidores Pulsar de Proveedores", lifespan=ciclo_de_vida)

    @app.get("/salud")
    def salud() -> JSONResponse:
        estado = {c.suscripcion: c.vivo() for c in consumidores}
        sano = bool(consumidores) and all(estado.values())
        return JSONResponse(
            status_code=200 if sano else 503,
            content={"estado": "ok" if sano else "degradado", "consumidores": estado},
        )

    return app
