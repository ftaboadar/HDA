import pulsar
import logging
from uuid import UUID
from pulsar.schema import JsonSchema
from app.application.commands import ActualizarScoringCommand
from app.application.handlers import ActualizarScoringHandler
from app.infrastructure.repositories import SQLiteScoringRepository
from app.infrastructure.messaging import TrabajoFinalizadoSchema
from app.domain.events import EventDispatcher, ScoringActualizadoEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PULSAR_URL = 'pulsar://localhost:6650'
TOPIC = 'persistent://public/default/trabajos.finalizado'
SUBSCRIPTION = 'scoring-worker-sub'

def on_scoring_actualizado(event):
    logger.info(f"[INTRA-EVENT] Scoring actualizado para {event.fotografo_id}: {event.nueva_puntuacion} at {event.fecha}")

def main():
    logger.info("Iniciando Worker de Scoring...")
    client = pulsar.Client(PULSAR_URL)
    
    try:
        consumer = client.subscribe(
            TOPIC, 
            subscription_name=SUBSCRIPTION,
            schema=JsonSchema(TrabajoFinalizadoSchema)
        )
        
        repository = SQLiteScoringRepository()
        dispatcher = EventDispatcher()
        dispatcher.subscribe(type(ScoringActualizadoEvent), on_scoring_actualizado)
        handler = ActualizarScoringHandler(repository, dispatcher)

        while True:
            msg = consumer.receive()
            try:
                data = msg.value()
                command = ActualizarScoringCommand(
                    fotografo_id=UUID(data.fotografo_id),
                    calificacion=data.calificacion
                )
                
                handler.handle(command)
                consumer.acknowledge(msg)
                
            except Exception as e:
                logger.error(f"Error procesando mensaje: {str(e)}")
                consumer.negative_acknowledge(msg)
                
    except KeyboardInterrupt:
        pass
    finally:
        client.close()

if __name__ == '__main__':
    main()
