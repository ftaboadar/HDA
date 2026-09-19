"""Puerto de publicación de eventos + tres adaptadores (RabbitMQ local /
Pub/Sub GCP / Apache Pulsar).

Esta es la pieza concreta que le da portabilidad al experimento: el resto del
código (API, worker/core.py) programa contra la interfaz `Publicador`, nunca
contra RabbitMQ, Pub/Sub o Pulsar directamente. Es la razón por la que
`experto-gcp` puede afirmar que el mecanismo (no solo el resultado) es
portable — y también, honestamente, dónde puede dejar de serlo: las garantías
de entrega/orden de RabbitMQ, Pub/Sub y Pulsar no son idénticas, ver
implementacion/proveedores/README.md (rutas relativas al repo, no al propio archivo), sección "Diferencias local vs. GCP".

`PublicadorPulsar` (sección 2.2, punto 1 del plan de Entrega 4,
`experimento-arquitectura/contexto/12-plan-entrega-4.md`) migra el transporte
de Proveedores de Pub/Sub a Pulsar — el contrato de la interfaz `Publicador`
no cambia de forma, solo se agrega un tercer adaptador concreto."""

from __future__ import annotations

import abc
import asyncio
import json
import os
import time


from app.common.logging_utils import configurar_logging, describir_mensaje, log_evento

logger = configurar_logging("common.publicador")

# Versión del contrato JSON de los mensajes de DISP-03 (solicitud, DLQ,
# proveedor.habilitado). Cambios ADITIVOS no la suben; un cambio que rompa
# a un consumidor existente sube a "2" y se publica en paralelo.
VERSION_ESQUEMA = "1"


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
        experimento).

        IMPORTANTE (bug de producción 2026-09-06, ver infra/pubsub.tf): este
        método NUNCA debe publicar sobre el mismo destino físico que
        `publicar_solicitud` — el worker consume solicitudes reales desde
        ahí (pull en RabbitMQ, push subscription en Pub/Sub) sin validar de
        forma estricta la forma de cada mensaje entrante. Cada adaptador
        concreto es responsable de mantener ambos destinos separados: en
        RabbitMQ vía routing key + binding de cola (la cola nunca se bindea
        a routing keys de eventos, así que quedan sin enrutar por diseño);
        en Pub/Sub vía un topic físicamente distinto y sin suscripción push
        activa (ver `eventos_integracion` en infra/pubsub.tf)."""


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
        #
        # Esto SÍ es seguro a diferencia del equivalente de Pub/Sub (ver
        # PublicadorPubSub.publicar_evento y el bug de 2026-09-06 en
        # infra/pubsub.tf): `cola_sol` en mq.py solo se bindea a routing
        # keys `verificacion.*`, así que un mensaje "proveedor.habilitado"
        # nunca llega al consumidor de solicitudes real, aunque comparta
        # exchange. Pub/Sub no tiene ese filtrado por routing key a nivel
        # de suscripción — por eso ahí sí hizo falta un topic físicamente
        # distinto.
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

    def __init__(
        self,
        project_id: str,
        topic_solicitudes: str,
        topic_fallidas: str,
        topic_eventos: str = "",
    ):
        from google.cloud import pubsub_v1

        self._cliente = pubsub_v1.PublisherClient()
        self._ruta_sol = (
            self._cliente.topic_path(project_id, topic_solicitudes) if topic_solicitudes else None
        )
        self._ruta_dlq = self._cliente.topic_path(project_id, topic_fallidas)
        # Topic FÍSICAMENTE distinto del de solicitudes (bug de producción
        # 2026-09-06, ver infra/pubsub.tf): la suscripción push del worker
        # está atada solo a "solicitudes", así que un evento de integración
        # publicado aquí nunca llega a /pubsub/push como si fuera una
        # verificación real.
        self._ruta_eventos = (
            self._cliente.topic_path(project_id, topic_eventos) if topic_eventos else None
        )

    async def _publicar(self, ruta: str, mensaje: dict, tipo_evento: str) -> None:
        # Atributos Pub/Sub = metadata del mensaje (equivalente a headers en
        # AsyncAPI): la versión del contrato viaja aquí, no en el cuerpo.
        atributos = {
            "tipo_evento": tipo_evento,
            "version_esquema": VERSION_ESQUEMA,
            "content_type": "application/json",
            "productor": os.environ.get("K_SERVICE", "proveedores"),
        }
        inicio = time.perf_counter()
        loop = asyncio.get_event_loop()
        message_id = await loop.run_in_executor(
            None,
            lambda: self._cliente.publish(ruta, json.dumps(mensaje).encode(), **atributos).result(),
        )
        log_evento(
            logger,
            "mensaje_publicado",
            **describir_mensaje(
                mensaje,
                canal="pubsub",
                topico=ruta.rsplit("/", 1)[-1],
                version_esquema=VERSION_ESQUEMA,
            ),
            tipo_evento=tipo_evento,
            message_id=message_id,
            atributos_mensaje=atributos,
            duracion_publicacion_ms=round((time.perf_counter() - inicio) * 1000, 1),
        )

    async def publicar_solicitud(self, mensaje: dict) -> None:
        if not self._ruta_sol:
            raise RuntimeError("PUBSUB_TOPIC_SOLICITUDES no configurado")
        await self._publicar(self._ruta_sol, mensaje, "SolicitudVerificacion")

    async def publicar_fallida(self, mensaje: dict) -> None:
        await self._publicar(self._ruta_dlq, mensaje, "VerificacionFallida")

    async def publicar_evento(self, routing_key: str, mensaje: dict) -> None:
        # Pub/Sub no tiene routing keys tipo AMQP — el routing_key viaja como
        # campo del mensaje. Publica a `eventos_integracion`
        # (infra/pubsub.tf), NUNCA al topic de solicitudes: hasta el
        # 2026-09-06 este método reutilizaba `self._ruta_sol`, y como la
        # suscripción push del worker está atada a ese mismo topic sin
        # filtro, cada `proveedor.habilitado` llegaba a
        # worker/push_handler.py como si fuera una verificación real y
        # reventaba con KeyError('verificacion_id') — ver commit que
        # introduce este comentario. Un topic dedicado por tipo de evento
        # de integración (en vez de uno compartido para todos) sigue siendo
        # la evolución natural si un bounded context real llega a consumir
        # esto, pero está fuera del alcance de este PoC (ver docstring de
        # la interfaz).
        if not self._ruta_eventos:
            raise RuntimeError("PUBSUB_TOPIC_EVENTOS no configurado")
        await self._publicar(
            self._ruta_eventos,
            {**mensaje, "routing_key": routing_key},
            mensaje.get("evento", routing_key),
        )


class PublicadorPulsar(Publicador):
    """Adaptador Apache Pulsar (sección 2.2, punto 1 del plan de Entrega 4):
    un productor por destino físico, igual que `PublicadorPubSub` — nunca un
    productor compartido entre solicitudes y eventos de integración (mismo
    cuidado explícito del bug de producción del 2026-09-06, ver
    `app/common/pulsar_topology.py`).

    El cliente `pulsar-client` (Python) es síncrono/bloqueante en `send()`;
    se despacha vía `run_in_executor`, mismo patrón que `PublicadorPubSub`
    usa para el cliente síncrono de `google-cloud-pubsub`, para no bloquear
    el loop de asyncio de FastAPI/el worker."""

    def __init__(
        self,
        service_url: str,
        topic_solicitudes: str,
        topic_fallidas: str,
        topic_eventos: str = "",
    ):
        import pulsar

        self._cliente = pulsar.Client(service_url)
        self._productor_sol = (
            self._cliente.create_producer(topic_solicitudes) if topic_solicitudes else None
        )
        self._productor_dlq = self._cliente.create_producer(topic_fallidas)
        # Tópico FÍSICAMENTE distinto del de solicitudes (bug de producción
        # 2026-09-06, ver docstring de app/common/pulsar_topology.py): la
        # suscripción pull del worker (worker/pulsar_consumer.py) está
        # atada solo a topic_solicitudes.
        self._productor_eventos = (
            self._cliente.create_producer(topic_eventos) if topic_eventos else None
        )

    async def _enviar(self, productor, mensaje: dict) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: productor.send(json.dumps(mensaje).encode()))

    async def publicar_solicitud(self, mensaje: dict) -> None:
        if not self._productor_sol:
            raise RuntimeError("PULSAR_TOPIC_SOLICITUDES no configurado")
        await self._enviar(self._productor_sol, mensaje)

    async def publicar_fallida(self, mensaje: dict) -> None:
        await self._enviar(self._productor_dlq, mensaje)

    async def publicar_evento(self, routing_key: str, mensaje: dict) -> None:
        # Igual que en Pub/Sub, Pulsar no tiene routing keys tipo AMQP — el
        # routing_key viaja como campo del mensaje, publicado exclusivamente
        # al tópico de eventos de integración, nunca al de solicitudes.
        if not self._productor_eventos:
            raise RuntimeError("PULSAR_TOPIC_EVENTOS no configurado")
        await self._enviar(self._productor_eventos, {**mensaje, "routing_key": routing_key})

    def cerrar(self) -> None:
        """Cierre explícito del cliente — no hay un hook de shutdown de
        FastAPI equivalente a `app.on_event("shutdown")` para el worker pull
        (ver worker/pulsar_consumer.py), así que cada punto de entrada es
        responsable de llamarlo en su propio `finally`."""
        self._cliente.close()
