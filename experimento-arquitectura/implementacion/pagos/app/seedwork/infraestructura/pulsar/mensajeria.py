import time
from typing import Any

from app.common.config import settings
from app.common.logging_utils import configurar_logging, log_evento
from app.infrastructure.messaging.esquemas import publicar_mensaje_generico

logger = configurar_logging("infrastructure.messaging.publicador_pulsar")

VERSION_ESQUEMA = "1"


class PublicadorPulsar:
    def __init__(self, service_url: str = None) -> None:
        self._service_url = service_url or settings.pulsar_service_url
        self._cliente: Any = None
        self._productores: dict = {}

    def _asegurar_productor(self, topic: str) -> Any:
        if topic in self._productores:
            return self._productores[topic]

        import pulsar
        from pulsar.schema import JsonSchema
        from app.infrastructure.messaging.esquemas import (
            PagoRetenidoMensaje,
            PagoRetencionFallidaMensaje,
            PagoLiberadoMensaje,
            PagoFallidoMensaje,
            PagoCompensadoMensaje,
        )

        if self._cliente is None:
            self._cliente = pulsar.Client(self._service_url)

        # Determinar schema según el topic
        schema = None
        if "pago.retenido" in topic:
            schema = JsonSchema(PagoRetenidoMensaje)
        elif "pago.retencion-fallida" in topic:
            schema = JsonSchema(PagoRetencionFallidaMensaje)
        elif "pago.liberado" in topic:
            schema = JsonSchema(PagoLiberadoMensaje)
        elif "pago.fallido" in topic:
            schema = JsonSchema(PagoFallidoMensaje)
        elif "pago.compensado" in topic:
            schema = JsonSchema(PagoCompensadoMensaje)

        productor = self._cliente.create_producer(topic, schema=schema)
        self._productores[topic] = productor
        return productor

    def publicar_evento(
        self,
        evento_registro: Any,
        topic: str,
        tipo_evento: str,
        correlation_id: str = "",
    ) -> None:
        productor = self._asegurar_productor(topic)

        inicio = time.perf_counter()

        message_id = publicar_mensaje_generico(
            productor=productor,
            mensaje=evento_registro,
            tipo_evento=tipo_evento,
            productor_nombre="pagos",
            correlation_id=correlation_id,
            version_esquema=VERSION_ESQUEMA,
        )

        log_evento(
            logger,
            "evento_publicado",
            detalle=True,
            topico=topic,
            tipo_evento=tipo_evento,
            message_id=str(message_id),
            duracion_ms=round((time.perf_counter() - inicio) * 1000, 1),
        )

    def cerrar(self) -> None:
        for p in self._productores.values():
            p.close()
        if self._cliente is not None:
            self._cliente.close()
