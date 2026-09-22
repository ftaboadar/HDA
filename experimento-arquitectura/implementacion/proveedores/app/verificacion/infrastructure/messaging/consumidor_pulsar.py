"""HUÉRFANO — superado por `app/worker/consumidor_trabajos_finalizado.py`,
no lo importa ningún punto de entrada real. Se conserva sin arreglar,
documentado, para dejar trazada la decisión (Entrega 5, hallazgo del
2026-09-22):

- Este archivo importaba `PulsarMensajeria` desde
  `app/seedwork/infraestructura/pulsar/mensajeria.py`, pero esa clase se
  llama `Mensajeria` y nunca tuvo un método `subscribe` (solo
  `publicar()`/`cerrar()`) — nunca pudo haber corrido.
- Llama a `RevalidarProveedor.ejecutar(proveedor_id, motivo=...)`, pero
  `RevalidarProveedor.ejecutar()` (ver su propio archivo) es un `pass`
  literal y su firma real solo acepta `proveedor_id` — ni siquiera con los
  imports arreglados este comando haría algo. `app/api/main.py` ya
  documenta por qué deliberadamente no se expone por HTTP.
- El consumidor real y correcto de `trabajos.finalizado` es
  `app/worker/consumidor_trabajos_finalizado.py`: mismo evento de
  integración, comando SÍ funcional (`RegistrarEventoTrabajoFinalizado`,
  un "skeleton de oír" deliberado — no completa la verificación
  automáticamente, eso es la Saga, fuera de alcance aún), imports
  correctos, y es el que `app/worker/main.py` arranca de verdad.

Arreglar el bug de `Mensajeria.subscribe` para revivir este archivo
duplicaría, con un comando que sigue siendo un stub, un consumidor que ya
existe y funciona con un comando real — se prefirió consolidar en uno
solo (menos superficie, mismo patrón DDD/hexagonal: el adaptador de
entrada llama a un comando de `application/`, nunca al ORM ni a la cola
directamente) en vez de arreglar y wire-ar el duplicado.

Imports corregidos solo para que el módulo sea estáticamente válido
(ruff F821) — el fallo real en tiempo de ejecución sigue siendo el
descrito arriba (`Mensajeria` no tiene `subscribe`), a propósito."""

import json
import logging

from app.seedwork.infraestructura.pulsar.mensajeria import Mensajeria
from app.verificacion.application.commands.revalidar_proveedor import RevalidarProveedor
from app.verificacion.domain.value_objects import MotivoRevalidacion


def _procesar_mensaje(consumer, msg, repo, publicador):
    try:
        data = json.loads(msg.data().decode("utf-8"))
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
        asyncio.run(
            comando.ejecutar(
                proveedor_id=proveedor_id,
                motivo=MotivoRevalidacion.ALTA_NUEVO_TECNICO,  # Usamos uno existente o un placeholder
            )
        )
        logging.info(f"Comando RevalidarProveedor disparado para {proveedor_id}")
    except Exception as e:
        logging.error(f"Error procesando mensaje pulsar: {e}")
        raise e


def iniciar_consumidor(service_url: str, repo, publicador):
    mensajeria = Mensajeria(service_url)

    def cb(consumer, msg):
        _procesar_mensaje(consumer, msg, repo, publicador)

    mensajeria.subscribe(
        topic="persistent://hda/gestion-trabajos/trabajos.finalizado",
        subscription_name="proveedores-trabajos.finalizado",
        callback=cb,
    )
