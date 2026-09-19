"""Adaptador de entrada — consumidor LIVIANO de `trabajos.finalizado`
(Gestión de Trabajos -> Proveedores, sección 2 punto 2 y sección 1.1 del plan
de Entrega 4).

Solo recibe el evento y lo registra vía el comando
`RegistrarEventoTrabajoFinalizado` — NUNCA toca el agregado `Verificacion`
ni el ORM directo (sección 4.0.1 del plan: el consumidor es un adaptador de
`infrastructure/`/`worker/`, que llama a un comando en `application/`), y
NUNCA completa la cadena de verificación automáticamente (eso es Entrega 5,
la Saga). Es la prueba de que Proveedores también puede RECIBIR eventos de
otro microservicio, no solo publicarlos (sección 2.1 del plan: "comunicación
real en ambos sentidos").

Tópico y namespace son propiedad de Gestión de Trabajos (Frans, sección 8
del plan) — este archivo solo consume, nunca administra esa topología (a
diferencia de `pulsar_topology.py`, que sí es dueño de la topología propia
de Proveedores)."""

import asyncio
import json

import pulsar

from app.application.commands.registrar_evento_trabajo_finalizado import (
    RegistrarEventoTrabajoFinalizado,
)
from app.common.config import settings
from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.infrastructure.persistence.eventos_recibidos_repository_sqlalchemy import (
    EventosRecibidosRepositorySQLAlchemy,
)

logger = configurar_logging("worker.consumidor_trabajos_finalizado")


async def _procesar_mensaje(mensaje, consumidor) -> None:
    loop = asyncio.get_event_loop()
    try:
        payload = json.loads(mensaje.data())
        comando = RegistrarEventoTrabajoFinalizado(EventosRecibidosRepositorySQLAlchemy())
        comando.ejecutar(payload)
        log_evento(
            logger,
            "evento_trabajo_finalizado_recibido",
            trabajo_id=payload.get("trabajo_id"),
        )
        await loop.run_in_executor(None, lambda: consumidor.acknowledge(mensaje))
    except Exception as exc:  # noqa: BLE001 — un mensaje malformado no debe tumbar el consumidor
        log_evento(
            logger,
            "evento_trabajo_finalizado_fallo_procesamiento",
            nivel="error",
            error=str(exc),
        )
        await loop.run_in_executor(None, lambda: consumidor.negative_acknowledge(mensaje))


async def main() -> None:
    Base.metadata.create_all(bind=engine)  # crea `eventos_recibidos` si no existe

    cliente = pulsar.Client(settings.pulsar_service_url)
    consumidor = cliente.subscribe(
        settings.pulsar_topic_trabajos_finalizado,
        subscription_name=settings.pulsar_suscripcion_trabajos_finalizado,
        consumer_type=pulsar.ConsumerType.Shared,
    )

    log_evento(
        logger,
        "consumidor_trabajos_finalizado_iniciado",
        topico=settings.pulsar_topic_trabajos_finalizado,
    )

    loop = asyncio.get_event_loop()
    try:
        while True:
            mensaje = await loop.run_in_executor(None, consumidor.receive)
            await _procesar_mensaje(mensaje, consumidor)
    finally:
        consumidor.close()
        cliente.close()


if __name__ == "__main__":
    asyncio.run(main())
