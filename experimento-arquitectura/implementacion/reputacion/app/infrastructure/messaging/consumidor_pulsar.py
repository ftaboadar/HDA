"""Consumidor PULL liviano de `trabajos.finalizado` -- evento de
INTEGRACIÓN publicado por Gestión de Trabajos vía Apache Pulsar (ver
experimento-arquitectura/contexto/12-plan-entrega-4.md, secciones 3 y 4).

Es un adaptador de infraestructura de ENTRADA: recibe el mensaje, lo
traduce a argumentos primitivos, y llama al comando de aplicación
`RegistrarEventoTrabajoFinalizado` -- NUNCA toca el agregado
`PerfilReputacion` ni el ORM directamente (misma regla que ya se auditó en
DISP-03, plan sección 4.0.1: el consumidor es un adaptador que llama a
`application/`, no una vía alterna hacia el dominio o la BD).

Alcance de esta entrega (plan, sección 1.1): solo "oír" y registrar la
llegada del evento -- no completar ninguna cadena de negocio. Eso es
trabajo de la Saga, Entrega 5."""

from __future__ import annotations

import json
import logging

import pulsar

from app.application.commands.registrar_evento_trabajo_finalizado import (
    RegistrarEventoTrabajoFinalizado,
)
from app.application.ports.registro_auditoria import IRegistroAuditoria
from app.common.config import settings

logger = logging.getLogger("reputacion.consumidor_pulsar")


def _procesar_mensaje(payload: dict, registro: IRegistroAuditoria) -> None:
    comando = RegistrarEventoTrabajoFinalizado(registro)
    comando.ejecutar(
        trabajo_id=payload["trabajo_id"],
        proveedor_id=payload["proveedor_id"],
        payload=payload,
    )


def correr_consumidor(registro: IRegistroAuditoria) -> None:
    """Loop pull bloqueante -- pensado para correr como proceso/contenedor
    separado (`python -m app.infrastructure.messaging.consumidor_pulsar`),
    análogo a `DISP-03/app/worker/main.py` (consumidor pull de RabbitMQ)."""
    cliente = pulsar.Client(settings.pulsar_service_url)
    consumidor = cliente.subscribe(
        settings.pulsar_topic_trabajos_finalizado,
        subscription_name=settings.pulsar_subscription,
        consumer_type=pulsar.ConsumerType.Shared,
    )
    logger.info(
        "Consumidor de trabajos.finalizado iniciado (topic=%s, subscription=%s)",
        settings.pulsar_topic_trabajos_finalizado,
        settings.pulsar_subscription,
    )
    try:
        while True:
            mensaje = consumidor.receive()
            try:
                payload = json.loads(mensaje.data())
                _procesar_mensaje(payload, registro)
                consumidor.acknowledge(mensaje)
            except Exception:  # noqa: BLE001 -- nunca tumbar el loop por un mensaje malo
                logger.exception(
                    "Fallo procesando mensaje de trabajos.finalizado -- se envía negative-ack "
                    "(Pulsar lo reintregará según su política de reintentos/DLQ de suscripción)"
                )
                consumidor.negative_acknowledge(mensaje)
    finally:
        cliente.close()


if __name__ == "__main__":
    from app.common.db import Base, engine
    from app.infrastructure.persistence.registro_auditoria_sqlalchemy import (
        RegistroAuditoriaSQLAlchemy,
    )

    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(bind=engine)
    correr_consumidor(RegistroAuditoriaSQLAlchemy())
