import asyncio
import json
import uuid
import logging
from app.infrastructure.messaging.esquemas import PublicarElegiblesRecord, ElegiblesCalculadosRecord
from app.common.publicador import PublicadorPulsar

logger = logging.getLogger(__name__)

async def procesar_publicar_elegibles(mensaje_pulsar, publicador: PublicadorPulsar):
    try:
        # Calcular puntajes de forma simulada
        proveedores_calculados = [
            {"id": str(uuid.uuid4()), "score": 95},
            {"id": str(uuid.uuid4()), "score": 88}
        ]
        
        # Parse incoming record (assuming it's a dict or Record)
        # If the pulsar message payload is bytes of JSON (which happens when using json.dumps in producer)
        # We need to load it. In GT it was produced via dataclass -> json.dumps -> bytes.
        try:
            data = json.loads(mensaje_pulsar.data())
        except Exception:
            data = mensaje_pulsar.value() # if schema was used in consumer
            
        if isinstance(data, dict):
            saga_id = data.get("saga_id", "")
            correlation_id = data.get("correlation_id", "")
            origen = data.get("origen", "")
            origen_id = data.get("origen_id", "")
        else:
            saga_id = data.saga_id
            correlation_id = data.correlation_id
            origen = data.origen
            origen_id = data.origen_id
            
        logger.info(f"Procesando PublicarElegibles para saga {saga_id}")

        evento_respuesta = ElegiblesCalculadosRecord(
            evento_id=str(uuid.uuid4()),
            saga_id=saga_id,
            correlation_id=correlation_id,
            origen=origen,
            origen_id=origen_id,
            proveedores=json.dumps(proveedores_calculados)
        )
        
        await publicador.publicar_comando_saga(
            topic="hda/proveedores/elegibles.listo",
            mensaje_record=evento_respuesta,
            tipo_evento="ElegiblesCalculados"
        )
    except Exception as e:
        logger.error(f"Error procesando PublicarElegibles: {e}")
