"""Adaptador de INTEGRACIÓN — implementa el puerto `IPublicador`
(application/ports/publicador.py) publicando sobre Apache Pulsar, el broker
elegido para toda la Entrega 4 (12-plan-entrega-4.md sección 3).

Distinción explícita dominio vs. integración (Regla 4 de
REGLAS-DURAS-rubrica-entrega-3.md, ver también
domain/trabajo/eventos.py): `TrabajoFinalizado` nace como evento de DOMINIO
dentro del agregado `Trabajo` y nunca importa nada de Pulsar. Es
`application/commands/crear_trabajo.py` quien decide traducirlo y
publicarlo aquí como evento de INTEGRACIÓN, serializado en un schema Avro
simple ad-hoc sobre el tópico `trabajos.finalizado`.

Decisión no obvia: el cliente y el productor de Pulsar se crean de forma
PEREZOSA (en el primer `publicar_trabajo_finalizado`, no en `__init__`) —
así la API puede levantarse en un entorno de desarrollo sin el cluster de
Pulsar corriendo todavía (lo construye Daniel por separado en
implementacion/pulsar-infra/, ver sección 3 del plan); si el cluster no
está disponible, la excepción de `pulsar-client` se propaga tal cual hacia
`crear_trabajo.py`, que ya la captura y solo la registra (ver docstring de
ese comando) — este adaptador no oculta el error, solo no construye el
cliente antes de que haga falta."""

from __future__ import annotations

from typing import Any

from app.application.ports.publicador import IPublicador
from app.common.config import settings
from app.domain.trabajo.eventos import TrabajoFinalizado


class PublicadorPulsar(IPublicador):
    def __init__(
        self, service_url: str | None = None, topic: str | None = None
    ) -> None:
        self._service_url = service_url or settings.pulsar_service_url
        self._topic = topic or settings.pulsar_topic_trabajos_finalizado
        self._cliente: Any = None
        self._productor: Any = None
        self._schema_cls: Any = None

    def _asegurar_productor(self) -> Any:
        if self._productor is not None:
            return self._productor

        # Import perezoso (mismo patrón que
        # implementacion/DISP-03/app/common/publicador.py con aio_pika /
        # google.cloud.pubsub): así `domain/` y `application/` -- e incluso
        # este módulo, si nunca se llega a publicar -- no requieren tener
        # `pulsar-client` instalado para poder importarse en un test.
        import pulsar
        from pulsar.schema import AvroSchema, Record, String

        class TrabajoFinalizadoAvro(Record):
            """Schema Avro simple ad-hoc (12-plan-entrega-4.md sección 4.2:
            Avro, no Protobuf, por compatibilidad nativa con el Schema
            Registry de Pulsar). Todos los campos son String por
            simplicidad de este skeleton -- el productor/consumidor real
            solo necesita acordar el contrato, no tipos numéricos nativos
            de Avro; monto viaja como string decimal para no perder
            precisión con floats."""

            trabajo_id = String()
            proveedor_id = String()
            monto = String()
            moneda = String()
            region = String()
            ocurrido_en = String()

        self._cliente = pulsar.Client(self._service_url)
        self._productor = self._cliente.create_producer(
            self._topic, schema=AvroSchema(TrabajoFinalizadoAvro)
        )
        self._schema_cls = TrabajoFinalizadoAvro
        return self._productor

    async def publicar_trabajo_finalizado(self, evento: TrabajoFinalizado) -> None:
        productor = self._asegurar_productor()
        mensaje = self._schema_cls(
            trabajo_id=str(evento.trabajo_id),
            proveedor_id=str(evento.proveedor_id),
            monto=str(evento.monto),
            moneda=evento.moneda,
            region=evento.region.value,
            ocurrido_en=evento.ocurrido_en.isoformat(),
        )
        productor.send(mensaje)

    def cerrar(self) -> None:
        if self._cliente is not None:
            self._cliente.close()
