from fastapi import FastAPI
import asyncio
import threading
import json
import pulsar
from app.common.config import settings
from app.workflow.application.handlers_saga import SagaHandlers
from app.workflow.infrastructure.persistence.saga_repository_sqlalchemy import (
    SagaRepositorySQLAlchemy,
)
from app.ciclo_vida.infrastructure.persistence.trabajo_repository_sqlalchemy import (
    TrabajoRepositorySQLAlchemy,
)
from app.infrastructure.messaging.publicador_pulsar import PublicadorPulsar

app = FastAPI()


@app.get("/salud")
def salud():
    return {"status": "ok", "service": "gestion-de-trabajos-worker"}


def start_worker():
    client = pulsar.Client(settings.pulsar_service_url)

    repo_saga = SagaRepositorySQLAlchemy()
    repo_trabajos = TrabajoRepositorySQLAlchemy()
    publicador = PublicadorPulsar()
    handlers = SagaHandlers(repo_saga, repo_trabajos, publicador)

    topics = [
        "persistent://hda/proveedores/agenda.confirmada",
        "persistent://hda/proveedores/agenda.rechazada",
        "persistent://hda/pagos/pago.retenido",
        "persistent://hda/pagos/pago.retencion-fallida",
        "persistent://hda/pagos/pago.liberado",
        "persistent://hda/pagos/pago.compensado",
    ]

    consumer = client.subscribe(
        topics,
        subscription_name="gestion-trabajos-saga-worker",
        consumer_type=pulsar.ConsumerType.Shared,
    )

    print("Worker consumiendo eventos de saga...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        msg = None
        try:
            msg = consumer.receive()
            props = msg.properties()
            payload = json.loads(msg.data().decode("utf-8"))

            tipo = props.get("tipo_evento", "")
            id_evento = props.get("id_evento", "")

            if tipo == "AgendaConfirmada" or "agenda.confirmada" in msg.topic_name():
                loop.run_until_complete(
                    handlers.handle_franja_reservada(payload, id_evento)
                )
            elif tipo == "AgendaRechazada" or "agenda.rechazada" in msg.topic_name():
                loop.run_until_complete(
                    handlers.handle_franja_rechazada(payload, id_evento)
                )
            elif tipo == "PagoRetenido" or "pago.retenido" in msg.topic_name():
                loop.run_until_complete(
                    handlers.handle_pago_retenido(payload, id_evento)
                )
            elif (
                tipo == "PagoRetencionFallida"
                or "pago.retencion-fallida" in msg.topic_name()
            ):
                loop.run_until_complete(
                    handlers.handle_pago_retencion_fallida(payload, id_evento)
                )
            elif tipo == "PagoLiberado" or "pago.liberado" in msg.topic_name():
                loop.run_until_complete(
                    handlers.handle_pago_liberado(payload, id_evento)
                )
            elif tipo == "PagoCompensado" or "pago.compensado" in msg.topic_name():
                loop.run_until_complete(
                    handlers.handle_pago_compensado(payload, id_evento)
                )

            consumer.acknowledge(msg)
        except Exception as e:
            print(f"Error procesando mensaje: {e}")
            if msg:
                consumer.negative_acknowledge(msg)


@app.on_event("startup")
def startup_event():
    from app.common.db import Base, engine

    Base.metadata.create_all(bind=engine)
    thread = threading.Thread(target=start_worker, daemon=True)
    thread.start()


def start_deadline_checker():
    repo_saga = SagaRepositorySQLAlchemy()
    repo_trabajos = TrabajoRepositorySQLAlchemy()
    publicador = PublicadorPulsar()
    handlers = SagaHandlers(repo_saga, repo_trabajos, publicador)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            loop.run_until_complete(handlers.check_deadlines())
        except Exception as e:
            print(f"Error revisando plazos: {e}")
        import time

        time.sleep(60)  # Revisar cada 60 segundos


@app.on_event("startup")
def startup_event_deadlines():
    thread = threading.Thread(target=start_deadline_checker, daemon=True)
    thread.start()
