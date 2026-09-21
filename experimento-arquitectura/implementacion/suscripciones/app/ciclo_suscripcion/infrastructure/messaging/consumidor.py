import json
import pulsar
from pulsar import ConsumerType
from app.common.config import settings
from app.common.db import SessionLocal
from app.ciclo_suscripcion.application.commands.procesar_trabajo_finalizado import ProcesarTrabajoFinalizadoCommand, ejecutar_procesar_trabajo_finalizado
from app.ciclo_suscripcion.infrastructure.persistence.repository import SuscripcionRepositorySQLAlchemy
from app.common.logging_utils import log_evento

def iniciar_consumidor():
    client = pulsar.Client(settings.pulsar_service_url)
    try:
        consumer = client.subscribe(
            settings.pulsar_topic_trabajos_finalizado,
            settings.pulsar_subscription,
            consumer_type=ConsumerType.Shared,
            schema=pulsar.schema.BytesSchema()
        )
        
        while True:
            msg = consumer.receive()
            try:
                payload = json.loads(msg.data().decode('utf-8'))
                props = msg.properties()
                id_evento = props.get("id_evento") or payload.get("id_evento", str(msg.message_id()))
                correlation_id = props.get("correlation_id") or payload.get("correlation_id", "")
                
                log_evento(
                    dominio="suscripciones",
                    subdominio="ciclo_suscripcion",
                    tipo_subdominio="core",
                    bounded_context="suscripciones",
                    capa="infrastructure",
                    tipo_mensaje="mensaje_recibido",
                    correlation_id=correlation_id,
                    extra={
                        "suscripcion": settings.pulsar_subscription,
                        "message_id": str(msg.message_id()),
                        "id_evento": id_evento
                    }
                )
                
                # Consumo fan-out del TrabajoFinalizado (MOD-03)
                # Extraemos datos relevantes del trabajo.
                # Como GT no conoce Suscripciones, esperamos que la metadata o el correlation_id identifique la suscripción
                # si fue un trabajo de suscripción. 
                # Si el payload tiene suscripcion_id, lo usamos.
                # Asumimos payload["suscripcion_id"] y payload["ciclo_id"]. Si no, intentamos correlation_id.
                suscripcion_id = payload.get("suscripcion_id", correlation_id)
                ciclo_id = payload.get("ciclo_id", "1")
                proveedor_id = payload.get("proveedor_id")
                
                if suscripcion_id and proveedor_id:
                    session = SessionLocal()
                    try:
                        repo = SuscripcionRepositorySQLAlchemy(session)
                        cmd = ProcesarTrabajoFinalizadoCommand(
                            suscripcion_id=suscripcion_id,
                            ciclo_id=ciclo_id,
                            proveedor_id=proveedor_id
                        )
                        ejecutar_procesar_trabajo_finalizado(cmd, repo)
                        session.commit()
                    except Exception as e:
                        session.rollback()
                        raise e
                    finally:
                        session.close()
                
                consumer.acknowledge(msg)
            except Exception as e:
                # Regla de idempotencia y dead-letter policy
                consumer.negative_acknowledge(msg)
    finally:
        client.close()
