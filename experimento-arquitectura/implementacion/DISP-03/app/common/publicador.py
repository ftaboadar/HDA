"""Puerto de publicación de eventos + dos adaptadores (RabbitMQ local / Pub/Sub GCP).

Esta es la pieza concreta que le da portabilidad al experimento: el resto del
código (API, worker/core.py) programa contra la interfaz `Publicador`, nunca
contra RabbitMQ o Pub/Sub directamente. Es la razón por la que
`experto-gcp` puede afirmar que el mecanismo (no solo el resultado) es
portable — y también, honestamente, dónde puede dejar de serlo: las garantías
de entrega/orden de RabbitMQ y Pub/Sub no son idénticas, ver
implementacion/DISP-03/README.md (rutas relativas al repo, no al propio archivo), sección "Diferencias local vs. GCP"."""

from __future__ import annotations

import abc
import asyncio
import json


class Publicador(abc.ABC):
    @abc.abstractmethod
    async def publicar_solicitud(self, mensaje: dict) -> None: ...

    @abc.abstractmethod
    async def publicar_fallida(self, mensaje: dict) -> None: ...

    @abc.abstractmethod
    async def publicar_evento(self, routing_key: str, mensaje: dict) -> None:
        """Publica un evento de integración genérico (ej. `proveedor.habilitado`,
        ver app/application/dispatcher_eventos_dominio.py) — a diferencia de
        `publicar_solicitud`/`publicar_fallida`, que tienen forma y destino
        fijos, este método existe para eventos de integración nuevos que no
        necesitan su propia cola/topic dedicado dentro del alcance de este
        PoC (los bounded contexts que consumirían `proveedor.habilitado`
        — Marketplace, Siniestros, Suscripciones — están fuera de este
        experimento)."""


class PublicadorRabbitMQ(Publicador):
    """Adaptador local: publica sobre los exchanges declarados en mq.py."""

    def __init__(self, exchange_solicitudes, exchange_dlx):
        self._exchange_sol = exchange_solicitudes
        self._exchange_dlx = exchange_dlx

    async def publicar_solicitud(self, mensaje: dict) -> None:
        import aio_pika

        await self._exchange_sol.publish(
            aio_pika.Message(body=json.dumps(mensaje).encode(), delivery_mode=2),
            routing_key=f"verificacion.{mensaje['tipo_verificador']}",
        )

    async def publicar_fallida(self, mensaje: dict) -> None:
        import aio_pika

        await self._exchange_dlx.publish(
            aio_pika.Message(body=json.dumps(mensaje).encode(), delivery_mode=2),
            routing_key="",
        )

    async def publicar_evento(self, routing_key: str, mensaje: dict) -> None:
        import aio_pika

        # Se publica sobre el mismo exchange de solicitudes con un routing
        # key propio (ej. "proveedor.habilitado") — no hay cola ligada a él
        # todavía en mq.py (los consumidores de este evento son otros
        # bounded contexts, fuera de alcance de DISP-03), así que el
        # mensaje queda sin enrutar por diseño: demuestra el mecanismo sin
        # requerir construir el consumidor.
        await self._exchange_sol.publish(
            aio_pika.Message(body=json.dumps(mensaje).encode(), delivery_mode=2),
            routing_key=routing_key,
        )


class PublicadorPubSub(Publicador):
    """Adaptador GCP: publica directamente a los topics de Pub/Sub
    provisionados por infra/pubsub.tf. El dead-letter real en producción lo
    gestiona la suscripción push (política de reintentos + dead_letter_policy
    en Terraform); publicar_fallida aquí es para el caso en que el propio
    código de aplicación decide enviar a DLQ tras agotar sus reintentos
    internos (ver worker/core.py), que es el camino principal en este PoC."""

    def __init__(self, project_id: str, topic_solicitudes: str, topic_fallidas: str):
        from google.cloud import pubsub_v1

        self._cliente = pubsub_v1.PublisherClient()
        self._ruta_sol = (
            self._cliente.topic_path(project_id, topic_solicitudes) if topic_solicitudes else None
        )
        self._ruta_dlq = self._cliente.topic_path(project_id, topic_fallidas)

    async def _publicar(self, ruta: str, mensaje: dict) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._cliente.publish(ruta, json.dumps(mensaje).encode()).result(),
        )

    async def publicar_solicitud(self, mensaje: dict) -> None:
        if not self._ruta_sol:
            raise RuntimeError("PUBSUB_TOPIC_SOLICITUDES no configurado")
        await self._publicar(self._ruta_sol, mensaje)

    async def publicar_fallida(self, mensaje: dict) -> None:
        await self._publicar(self._ruta_dlq, mensaje)

    async def publicar_evento(self, routing_key: str, mensaje: dict) -> None:
        # Pub/Sub no tiene routing keys tipo AMQP — se reutiliza el topic de
        # solicitudes y el routing_key viaja como campo del mensaje. Un
        # topic dedicado por tipo de evento de integración es la evolución
        # natural si un bounded context real llega a consumir esto, pero
        # está fuera del alcance de este PoC (ver docstring de la interfaz).
        if not self._ruta_sol:
            raise RuntimeError("PUBSUB_TOPIC_SOLICITUDES no configurado")
        await self._publicar(self._ruta_sol, {**mensaje, "routing_key": routing_key})
