"""Doble del CRM SaaS externo "Gestión de Agentes" (DISP-02, ver
`experimento-arquitectura/contexto/escenarios_calidad.md`, fila DISP-02).

Distinto de los mocks existentes (`DISP-03/app/mocks/main.py`,
`mocks-pagos/app/common.py`), que solo simulan latencia/fallas: este mock
hace cumplir un **límite de tasa real** (ventana deslizante de 1s) sobre
`POST /webhooks`, respondiendo `429` + `Retry-After` cuando se supera —
confirmado por exploración previa que ningún mock del repo tenía hoy este
modo. Es lo que le da al `ThrottlerCrm`
(`gestion-de-trabajos/app/infrastructure/messaging/throttler.py`) algo real
contra qué dosificar, en vez de un doble que siempre responde 200.

Mismo patrón de control en caliente que los otros mocks
(`POST /_control/config`, `GET /_control/estado`, `GET /salud`), consumido
por los casos de prueba de carga
(`gestion-de-trabajos/tests/integracion/test_disp02_throttler.py`).

Nota de concurrencia: el estado (ventana deslizante) es un `list[float]` en
memoria protegido por un `asyncio.Lock` — correcto para un único proceso
`uvicorn` (sin `--workers > 1`), que es como se ejecuta este mock en
`docker-compose` (ver Dockerfile/docker-compose.yml). Coordinar el límite
entre varios procesos/réplicas del mock requeriría un contador compartido
(ej. Redis) — fuera de alcance de este doble de prueba."""

import asyncio
import time

from fastapi import FastAPI, Response
from pydantic import BaseModel

app = FastAPI(title="Mock — CRM Gestión de Agentes")

# Límite de tasa (requests/segundo) que este mock hace cumplir sobre
# POST /webhooks. Configurable en caliente vía POST /_control/config, nunca
# hardcodeado en un caso de prueba.
estado: dict[str, int] = {"limite_rps": 50}

# Ventana deslizante de 1s: timestamps (time.monotonic()) de los requests
# aceptados dentro del último segundo. Lista simple (no una estructura más
# sofisticada tipo deque+contador) porque a la escala de este PoC (decenas
# de req/s) el costo de podar por el frente es despreciable, y prioriza
# claridad sobre performance de la doble.
_ventana: list[float] = []
_lock = asyncio.Lock()

# Segundos que el mock le pide al cliente esperar antes de reintentar
# cuando se supera el límite — valor fijo pequeño, tal como pide el
# encargo de esta tarea (no requiere ser dinámico para que el escenario
# sea representativo).
RETRY_AFTER_S = 1


class ConfigMock(BaseModel):
    limite_rps: int


class WebhookPayload(BaseModel):
    novedad_id: str
    trabajo_id: str
    descripcion: str
    intentos: int


def _purgar_ventana(ahora: float) -> None:
    corte = ahora - 1.0
    while _ventana and _ventana[0] < corte:
        _ventana.pop(0)


@app.get("/salud")
async def salud():
    return {"estado": "ok", "mock": "crm-gestion-agentes"}


@app.post("/_control/config")
async def control_config(cfg: ConfigMock, response: Response):
    if cfg.limite_rps <= 0:
        response.status_code = 400
        return {"error": "limite_rps debe ser positivo"}
    estado["limite_rps"] = cfg.limite_rps
    return {"limite_rps": estado["limite_rps"]}


@app.get("/_control/estado")
async def control_estado():
    async with _lock:
        ahora = time.monotonic()
        _purgar_ventana(ahora)
        return {
            "limite_rps": estado["limite_rps"],
            "requests_en_ventana_actual": len(_ventana),
        }


@app.post("/webhooks")
async def webhooks(payload: WebhookPayload, response: Response):
    """Endpoint de negocio que llama `AdaptadorGestionAgentesHttp`. Cuenta
    requests en la ventana deslizante de 1s; si se supera `limite_rps`,
    responde 429 con `Retry-After`; si no, 200 con `{"recibido": true}` y
    registra el request en la ventana."""
    async with _lock:
        ahora = time.monotonic()
        _purgar_ventana(ahora)
        if len(_ventana) >= estado["limite_rps"]:
            response.status_code = 429
            response.headers["Retry-After"] = str(RETRY_AFTER_S)
            return {
                "error": "rate_limited",
                "limite_rps": estado["limite_rps"],
                "novedad_id": payload.novedad_id,
            }
        _ventana.append(ahora)
        return {"recibido": True, "novedad_id": payload.novedad_id}
