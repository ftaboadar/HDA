import json
import pulsar
from app.common.config import settings
from app.ciclo_suscripcion.domain.events import CicloSuscripcionGenerado
from app.common.logging_utils import log_evento

def publicar_ciclo_suscripcion(evento: CicloSuscripcionGenerado):
    client = pulsar.Client(settings.pulsar_service_url)
    try:
        producer = client.create_producer(
            settings.pulsar_topic_ciclo_suscripcion,
            schema=pulsar.schema.BytesSchema()
        )
        # Segun la regla de mensajeria: JSON plano
        payload = {
            "tipo_evento": "CicloSuscripcion",
            "version_esquema": "1",
            "content_type": "application/json",
            "productor": "suscripciones",
            "id_evento": evento.id_evento,
            "correlation_id": evento.suscripcion_id, # asumiendo que la suscripcion_id inicia el journey
            "suscripcion_id": evento.suscripcion_id,
            "ciclo_id": evento.ciclo_id,
            "proveedor_id": evento.proveedor_id,
            "es_primer_ciclo": evento.es_primer_ciclo,
            "dia_semana": evento.dia_semana,
            "bloque": evento.bloque
        }
        
        msg_id = producer.send(
            json.dumps(payload).encode('utf-8'),
            properties={
                "tipo_evento": "CicloSuscripcion",
                "version_esquema": "1",
                "content_type": "application/json",
                "productor": "suscripciones",
                "id_evento": evento.id_evento,
                "correlation_id": evento.suscripcion_id
            }
        )
        
        log_evento(
            dominio="suscripciones",
            subdominio="ciclo_suscripcion",
            tipo_subdominio="core",
            bounded_context="suscripciones",
            capa="infrastructure",
            tipo_mensaje="mensaje_publicado",
            correlation_id=evento.suscripcion_id,
            extra={
                "canal": "pulsar",
                "topico": settings.pulsar_topic_ciclo_suscripcion,
                "message_id": str(msg_id),
                "tipo_evento": "CicloSuscripcion"
            }
        )
    finally:
        client.close()
