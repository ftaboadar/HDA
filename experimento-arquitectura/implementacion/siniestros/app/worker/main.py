import pulsar
from pulsar.schema import JsonSchema
from pydantic import BaseModel
import json
import logging
from app.infrastructure.database import SessionLocal
from app.infrastructure.repositories import SiniestroRepository
from app.application.handlers import CommandHandler, MessagePublisher
from app.application.commands import ProcesarFacturaCommand, CompensarReservaCommand

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComandoFacturacion(BaseModel):
    siniestro_id: str
    factura_id: str
    monto: float

def start_worker():
    client = pulsar.Client('pulsar://localhost:6650')
    
    consumer_facturacion = client.subscribe(
        'comandos-facturacion-gt', 
        subscription_name='siniestros-worker',
        schema=pulsar.schema.JsonSchema(ComandoFacturacion)
    )

    consumer_compensacion = client.subscribe(
        'siniestros-events',
        subscription_name='siniestros-compensacion-worker'
    )

    db = SessionLocal()
    repo = SiniestroRepository(db)
    publisher = MessagePublisher()
    handler = CommandHandler(repo, publisher)

    logger.info("Iniciando Siniestros Worker...")
    try:
        while True:
            try:
                msg_fact = consumer_facturacion.receive(timeout_millis=100)
                data = msg_fact.value()
                cmd = ProcesarFacturaCommand(
                    siniestro_id=data.siniestro_id, factura_id=data.factura_id, monto=data.monto
                )
                handler.handle_procesar_factura(cmd)
                consumer_facturacion.acknowledge(msg_fact)
            except Exception:
                pass
            
            try:
                msg_comp = consumer_compensacion.receive(timeout_millis=100)
                data = json.loads(msg_comp.data().decode('utf-8'))
                if "CompensacionReservaRequerida" in str(data):
                    cmd_comp = CompensarReservaCommand(
                        siniestro_id=data.get("siniestro_id"),
                        monto_adicional=data.get("monto_compensacion")
                    )
                    handler.handle_compensar_reserva(cmd_comp)
                consumer_compensacion.acknowledge(msg_comp)
            except Exception:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        client.close()
        db.close()

if __name__ == "__main__":
    start_worker()
