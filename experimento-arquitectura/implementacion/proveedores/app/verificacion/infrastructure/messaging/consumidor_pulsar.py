import json
import logging
from app.seedwork.infraestructura.pulsar.mensajeria import PulsarMensajeria
from app.verificacion.application.commands.revalidar_proveedor import RevalidarProveedor
from app.domain.verificacion.value_objects import MotivoRevalidacion

def _procesar_mensaje(consumer, msg, repo, publicador):
    try:
        data = json.loads(msg.data().decode('utf-8'))
        logging.info(f"Mensaje recibido en trabajos.finalizado: {data}")
        # Validar y extraer id_proveedor o similar
        proveedor_id = data.get("proveedor_id")
        if not proveedor_id:
            logging.warning("El evento trabajos.finalizado no contiene proveedor_id")
            return
            
        import asyncio
        comando = RevalidarProveedor(repo, publicador)
        # Disparamos comando, asumiendo motivo es TRABAJO_FINALIZADO o similar
        # Fallback a VENCIMIENTO_CERTIFICADO si no hay, pero crearemos uno
        asyncio.run(comando.ejecutar(
            proveedor_id=proveedor_id,
            motivo=MotivoRevalidacion.ALTA_NUEVO_TECNICO # Usamos uno existente o un placeholder
        ))
        logging.info(f"Comando RevalidarProveedor disparado para {proveedor_id}")
    except Exception as e:
        logging.error(f"Error procesando mensaje pulsar: {e}")
        raise e

def iniciar_consumidor(service_url: str, repo, publicador):
    mensajeria = PulsarMensajeria(service_url)
    def cb(consumer, msg):
        _procesar_mensaje(consumer, msg, repo, publicador)
        
    mensajeria.subscribe(
        topic="persistent://hda/gestion-trabajos/trabajos.finalizado",
        subscription_name="proveedores-trabajos.finalizado",
        callback=cb
    )
