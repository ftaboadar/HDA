"""Topología de RabbitMQ para el transporte local.

El mensaje que cruza `verificacion.exchange` es un evento de INTEGRACIÓN entre el
adaptador de entrada (API) y el adaptador de procesamiento (worker) del mismo
servicio — se mantiene deliberadamente "gordo" (incluye proveedor_id y
tipo_verificador completos) para que el worker no necesite una consulta
adicional a la BD antes de poder actuar (Regla 4 de la rúbrica: distinguir el
tipo de evento y su forma explícitamente)."""

import aio_pika
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from app.common.config import settings


@retry(
    reraise=True,
    stop=stop_after_attempt(8),
    wait=wait_exponential_jitter(initial=0.5, max=10),
)
async def conectar() -> aio_pika.RobustConnection:
    """Reintenta la conexión inicial con backoff: el healthcheck de RabbitMQ
    en docker-compose garantiza el orden de arranque, pero no que el listener
    AMQP esté aceptando conexiones en el milisegundo exacto en que este
    servicio arranca (carrera observada en CI, donde el runner es más lento
    y variable que en desarrollo local)."""
    return await aio_pika.connect_robust(settings.rabbitmq_url)


async def declarar_topologia(canal: aio_pika.Channel):
    exchange_sol = await canal.declare_exchange(
        settings.exchange_solicitudes, aio_pika.ExchangeType.TOPIC, durable=True
    )
    exchange_dlx = await canal.declare_exchange(
        settings.exchange_dlq, aio_pika.ExchangeType.FANOUT, durable=True
    )

    cola_sol = await canal.declare_queue(settings.cola_solicitudes, durable=True)
    await cola_sol.bind(exchange_sol, routing_key="verificacion.#")

    cola_dlq = await canal.declare_queue(settings.cola_dlq, durable=True)
    await cola_dlq.bind(exchange_dlx)

    return exchange_sol, exchange_dlx, cola_sol, cola_dlq
