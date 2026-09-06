"""Handler push de Pub/Sub para Cloud Run (entorno GCP).

Equivalente funcional de worker/main.py pero disparado por HTTP (push
subscription, ver infra/pubsub.tf) en vez de un loop de consumo pull. La
lógica de reintentos/backoff es la misma (worker/core.py) — solo cambia el
transporte, que es justo el punto que experto-gcp debe dejar documentado
como diferencia local↔GCP. Igual que worker/main.py, cada intento se
registra vía el comando `RegistrarIntento` — no se escribe el ORM directo.

Nota: siempre respondemos 200, incluso cuando la verificación termina en DLQ,
porque procesar_verificacion() ya agotó sus propios reintentos internamente.
Devolver un error HTTP aquí haría que Pub/Sub reintregue el mensaje y
duplique reintentos a dos niveles distintos (el nuestro y el de la
suscripción), lo cual no es lo que DISP-03 pide.

Nota sobre concurrencia (investigación CP-2 contra GCP real, ver
experimento-arquitectura/): a diferencia de worker/main.py, este handler NO
usa un asyncio.Semaphore explícito. Es una decisión deliberada, no un
descuido: cada POST /pubsub/push que llega lo despacha uvicorn/FastAPI como
su propia task de asyncio, y procesar_verificacion() llama al puerto externo
con httpx.AsyncClient (no bloqueante) — así que varias verificaciones ya se
procesan de forma concurrente dentro de una misma instancia caliente, sin
necesidad de un semáforo de aplicación equivalente al de worker/main.py (ese
semáforo allá cumple otro propósito: acotar cuántos mensajes de RabbitMQ se
sacan a la vez para no agotar memoria/prefetch, no evitar bloqueo mutuo).
Cuando CP-2 midió 4.21s contra un umbral de 1.5s en GCP, la causa más
probable no era este handler sino cold start de Cloud Run
(min_instance_count=0 dejaba al worker frío; ver infra/cloudrun.tf, donde se
fijó min_instance_count=1 y max_instance_request_concurrency explícito para
que una ráfaga de 6 mensajes no dispare varias instancias frías en paralelo).
Si una futura corrida instrumentada muestra que el verdadero cuello de
botella SÍ está aquí (ej. `repo.guardar()` es una llamada síncrona a
SQLAlchemy que bloquea el event loop durante cada escritura — ver
verificacion_repository_sqlalchemy.py — y eso pesa más de lo esperado bajo
la latencia real de Cloud SQL), ahí sí correspondería revisar si conviene
paralelizar esa escritura o acotar concurrencia por instancia."""

import base64
import json
import os

from fastapi import FastAPI, Request

from app.application.commands.registrar_intento import RegistrarIntento
from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.publicador import PublicadorPubSub
from app.domain.verificacion.value_objects import ResultadoIntento
from app.infrastructure.persistence.verificacion_repository_sqlalchemy import (
    VerificacionRepositorySQLAlchemy,
)
from app.worker.core import procesar_verificacion

logger = configurar_logging("worker.push_handler")
app = FastAPI(title="Verificación — Worker (Cloud Run / Pub/Sub push)")

_publicador: PublicadorPubSub | None = None


@app.on_event("startup")
async def startup() -> None:
    global _publicador
    Base.metadata.create_all(bind=engine)
    _publicador = PublicadorPubSub(
        project_id=os.environ["GCP_PROJECT"],
        topic_solicitudes=os.environ.get("PUBSUB_TOPIC_SOLICITUDES", ""),
        topic_fallidas=os.environ["PUBSUB_TOPIC_FALLIDAS"],
    )


@app.get("/salud")
async def salud():
    return {"estado": "ok"}


@app.post("/pubsub/push")
async def recibir_push(request: Request):
    assert _publicador is not None
    envoltura = await request.json()
    datos_b64 = envoltura["message"]["data"]
    payload = json.loads(base64.b64decode(datos_b64))
    verificacion_id = payload["verificacion_id"]

    resultado = await procesar_verificacion(
        verificacion_id, payload["proveedor_id"], payload["tipo_verificador"]
    )

    repo = VerificacionRepositorySQLAlchemy()
    comando = RegistrarIntento(repo, _publicador)
    for intento in resultado.detalle_intentos:
        await comando.ejecutar(
            verificacion_id=verificacion_id,
            resultado=ResultadoIntento.EXITOSO if intento.exito else ResultadoIntento.FALLIDO,
            duracion_ms=intento.duracion_ms,
            error=intento.error,
        )

    log_evento(
        logger,
        "verificacion_procesada_push",
        verificacion_id=verificacion_id,
        exito=resultado.exito,
    )
    return {"estado": "procesado"}
