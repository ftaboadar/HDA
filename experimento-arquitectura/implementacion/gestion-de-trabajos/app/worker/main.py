from fastapi import FastAPI
import asyncio
import threading
import json
import pulsar
from app.common.config import settings
from app.application.handlers_saga import SagaHandlers
from app.infrastructure.persistence.saga_repository_sqlalchemy import SagaRepositorySQLAlchemy
from app.infrastructure.persistence.trabajo_repository_sqlalchemy import TrabajoRepositorySQLAlchemy
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
        "hda/proveedores/agenda.reservada",
        "hda/proveedores/agenda.rechazada",
        "hda/pagos/pago.retenido",
        "hda/pagos/pago.retencion_fallida"
    ]
    
    consumer = client.subscribe(topics, subscription_name="saga-worker-sub")
    
    print("Worker consumiendo eventos de saga...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        msg = None
        try:
            msg = consumer.receive()
            props = msg.properties()
            # Asumimos contenido JSON plano
            payload = json.loads(msg.data().decode('utf-8'))
            
            tipo = props.get("tipo_evento", "")
            
            if tipo == "FranjaReservada":
                loop.run_until_complete(handlers.handle_franja_reservada(payload))
            elif tipo == "FranjaRechazada":
                loop.run_until_complete(handlers.handle_franja_rechazada(payload))
            elif tipo == "PagoRetenido":
                loop.run_until_complete(handlers.handle_pago_retenido(payload))
            elif tipo == "PagoRetencionFallida":
                loop.run_until_complete(handlers.handle_pago_retencion_fallida(payload))
            
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
