"""Handler push de Pub/Sub para Cloud Run (entorno GCP).

Equivalente funcional de worker/main.py pero disparado por HTTP (push
subscription, ver infra/pubsub.tf) en vez de un loop de consumo pull. La
lógica de reintentos/backoff es la misma (worker/core.py) — solo cambia el
transporte, que es justo el punto que experto-gcp debe dejar documentado
como diferencia local↔GCP.

Nota: siempre respondemos 200, incluso cuando la verificación termina en DLQ,
porque procesar_verificacion() ya agotó sus propios reintentos internamente.
Devolver un error HTTP aquí haría que Pub/Sub reintregue el mensaje y
duplique reintentos a dos niveles distintos (el nuestro y el de la
suscripción), lo cual no es lo que DISP-03 pide."""

import base64
import json
import os

from fastapi import FastAPI, Request

from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.publicador import PublicadorPubSub
from app.worker.core import procesar_verificacion
from app.worker.main import actualizar_db

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
    envoltura = await request.json()
    datos_b64 = envoltura["message"]["data"]
    payload = json.loads(base64.b64decode(datos_b64))

    resultado = await procesar_verificacion(
        payload["verificacion_id"], payload["proveedor_id"], payload["tipo_verificador"]
    )
    actualizar_db(
        payload["verificacion_id"], resultado.exito, resultado.intentos, resultado.motivo_falla
    )
    if not resultado.exito:
        assert _publicador is not None
        await _publicador.publicar_fallida(
            {
                **payload,
                "motivo_falla": resultado.motivo_falla,
                "intentos": resultado.intentos,
            }
        )

    log_evento(
        logger,
        "verificacion_procesada_push",
        verificacion_id=payload["verificacion_id"],
        exito=resultado.exito,
    )
    return {"estado": "procesado"}
