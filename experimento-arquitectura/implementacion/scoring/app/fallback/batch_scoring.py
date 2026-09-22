import argparse
import json
import logging
from uuid import UUID
from app.application.commands import ActualizarScoringCommand
from app.application.handlers import ActualizarScoringHandler
from app.infrastructure.repositories import SQLiteScoringRepository
from app.domain.events import EventDispatcher, ScoringActualizadoEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def on_scoring_actualizado(event):
    logger.info(f"[BATCH-INTRA-EVENT] Fotógrafo {event.fotografo_id} -> Nueva puntuación: {event.nueva_puntuacion}")

def procesar_lote(archivo_path: str):
    repository = SQLiteScoringRepository()
    dispatcher = EventDispatcher()
    dispatcher.subscribe(type(ScoringActualizadoEvent), on_scoring_actualizado)
    handler = ActualizarScoringHandler(repository, dispatcher)
    
    try:
        with open(archivo_path, 'r') as f:
            for linea in f:
                if not linea.strip(): continue
                try:
                    data = json.loads(linea)
                    command = ActualizarScoringCommand(
                        fotografo_id=UUID(data['fotografo_id']),
                        calificacion=float(data.get('calificacion', 5.0))
                    )
                    handler.handle(command)
                except Exception as e:
                    logger.error(f"Error procesando {linea.strip()}: {e}")
    except FileNotFoundError:
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=str, required=True)
    args = parser.parse_args()
    procesar_lote(args.file)
