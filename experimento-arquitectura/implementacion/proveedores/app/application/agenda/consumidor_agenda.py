import json
import uuid
import logging
from app.infrastructure.messaging.esquemas import FranjaReservadaRecord
from app.common.publicador import PublicadorPulsar

logger = logging.getLogger(__name__)

async def procesar_reservar_franja(mensaje_pulsar, publicador: PublicadorPulsar):
    try:
        try:
            data = json.loads(mensaje_pulsar.data())
        except Exception:
            data = mensaje_pulsar.value()
            
        if isinstance(data, dict):
            saga_id = data.get("saga_id", "")
            correlation_id = data.get("correlation_id", "")
            proveedor_id = data.get("proveedor_id", "")
            tecnico_id = data.get("tecnico_id", "")
        else:
            saga_id = data.saga_id
            correlation_id = data.correlation_id
            proveedor_id = data.proveedor_id
            tecnico_id = data.tecnico_id
            
        logger.info(f"Procesando ReservarFranja para saga {saga_id}")

        # Simular reserva exitosa
        reserva_id = str(uuid.uuid4())
        
        evento_respuesta = FranjaReservadaRecord(
            evento_id=str(uuid.uuid4()),
            saga_id=saga_id,
            correlation_id=correlation_id,
            reserva_id=reserva_id,
            monto=150.0,
            moneda="COP"
        )
        
        await publicador.publicar_comando_saga(
            topic="hda/proveedores/franja.reservada",
            mensaje_record=evento_respuesta,
            tipo_evento="FranjaReservada"
        )
    except Exception as e:
        logger.error(f"Error procesando ReservarFranja: {e}")
