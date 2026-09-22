import asyncio
import json

from app.common.db import SessionLocal
from app.infrastructure.persistence.models_db import OutboxEventORM
from app.seedwork.infraestructura.pulsar.mensajeria import PublicadorPulsar
from app.common.logging_utils import configurar_logging

logger = configurar_logging("worker.outbox_publisher")

class OutboxPublisher:
    def __init__(self, publicador: PublicadorPulsar, interval_seconds: int = 5):
        self._publicador = publicador
        self._interval_seconds = interval_seconds
        self._corriendo = False

    async def iniciar(self):
        self._corriendo = True
        logger.info("Outbox publisher iniciado")
        while self._corriendo:
            try:
                await asyncio.to_thread(self._procesar_eventos)
            except Exception as e:
                logger.error(f"Error procesando outbox: {e}")
            await asyncio.sleep(self._interval_seconds)

    def _procesar_eventos(self):
        with SessionLocal() as db:
            eventos = db.query(OutboxEventORM).filter(OutboxEventORM.published == "FALSE").order_by(OutboxEventORM.created_at).limit(50).all()
            for evento in eventos:
                try:
                    payload_dict = json.loads(evento.payload)
                    
                    from app.infrastructure.messaging.esquemas import (
                        PagoRetenidoMensaje, PagoRetencionFallidaMensaje,
                        PagoLiberadoMensaje, PagoFallidoMensaje, PagoCompensadoMensaje
                    )
                    
                    if evento.event_type == "PagoRetenido":
                        msg = PagoRetenidoMensaje(**payload_dict)
                    elif evento.event_type == "PagoRetencionFallida":
                        msg = PagoRetencionFallidaMensaje(**payload_dict)
                    elif evento.event_type == "PagoLiberado":
                        msg = PagoLiberadoMensaje(**payload_dict)
                    elif evento.event_type == "PagoFallido":
                        msg = PagoFallidoMensaje(**payload_dict)
                    elif evento.event_type == "PagoCompensado":
                        msg = PagoCompensadoMensaje(**payload_dict)
                    else:
                        raise ValueError(f"Evento desconocido: {evento.event_type}")
                    
                    self._publicador.publicar_evento(
                        msg,
                        topic=evento.topic,
                        tipo_evento=evento.event_type,
                        correlation_id=evento.correlation_id
                    )
                    evento.published = "TRUE"
                except Exception as e:
                    logger.error(f"Error publicando evento {evento.id}: {e}")
            
            db.commit()

    def detener(self):
        self._corriendo = False
