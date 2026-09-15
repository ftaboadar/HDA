"""Adaptador de INTEGRACIÓN — implementa el puerto `IPublicador`
(application/ports/publicador.py) publicando sobre Apache Pulsar, el broker
elegido para toda la Entrega 4 (12-plan-entrega-4.md sección 3).

Distinción explícita dominio vs. integración (Regla 4 de
REGLAS-DURAS-rubrica-entrega-3.md, ver también
domain/trabajo/eventos.py): `TrabajoFinalizado` nace como evento de DOMINIO
dentro del agregado `Trabajo` y nunca importa nada de Pulsar. Es
`application/commands/crear_trabajo.py` quien decide traducirlo y
publicarlo aquí como evento de INTEGRACIÓN sobre el tópico
`trabajos.finalizado`.

CORRECCIÓN (encontrada corriendo contra un cluster de Pulsar real, no en
tests): la versión anterior de este archivo serializaba con
`pulsar.schema.AvroSchema`. Eso rompía por DOS motivos, no solo uno:
1. `pulsar-client==3.5.0` sin el extra `[avro]` no trae `fastavro` —
   `create_producer(..., schema=AvroSchema(...))` lanzaba
   "Avro library support was not found" en cada intento de publicar.
2. Aunque se instalara `fastavro`, `reputacion/app/infrastructure/messaging/consumidor_pulsar.py`
   (el consumidor real de este tópico) hace `json.loads(mensaje.data())` —
   espera JSON plano, no bytes Avro con metadata de schema. Los dos
   servicios son de equipos distintos y nunca se probaron juntos contra un
   broker real hasta ahora.

Se unifica al mismo contrato que ya usa `DISP-03/app/common/publicador.py`
para Pulsar (JSON plano vía `producer.send(json.dumps(mensaje).encode())`,
despachado con `run_in_executor` porque el cliente de `pulsar-client` es
síncrono/bloqueante) — un solo formato de mensaje entre los tres servicios
que hablan Pulsar en este proyecto, en vez de que cada uno invente el
suyo.

Decisión no obvia: el cliente y el productor de Pulsar se crean de forma
PEREZOSA (en el primer `publicar_trabajo_finalizado`, no en `__init__`) —
así la API puede levantarse en un entorno de desarrollo sin el cluster de
Pulsar corriendo todavía; si el cluster no está disponible, la excepción de
`pulsar-client` se propaga tal cual hacia `crear_trabajo.py`, que ya la
captura y solo la registra (ver docstring de ese comando) — este adaptador
no oculta el error, solo no construye el cliente antes de que haga falta."""

from __future__ import annotations

import asyncio
import json
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

    def _asegurar_productor(self) -> Any:
        if self._productor is not None:
            return self._productor

        # Import perezoso (mismo patrón que
        # implementacion/DISP-03/app/common/publicador.py con aio_pika /
        # google.cloud.pubsub): así `domain/` y `application/` -- e incluso
        # este módulo, si nunca se llega a publicar -- no requieren tener
        # `pulsar-client` instalado para poder importarse en un test.
        import pulsar

        self._cliente = pulsar.Client(self._service_url)
        self._productor = self._cliente.create_producer(self._topic)
        return self._productor

    async def publicar_trabajo_finalizado(self, evento: TrabajoFinalizado) -> None:
        productor = self._asegurar_productor()
        mensaje = {
            "trabajo_id": str(evento.trabajo_id),
            "proveedor_id": str(evento.proveedor_id),
            "monto": str(evento.monto),
            "moneda": evento.moneda,
            "region": evento.region.value,
            "ocurrido_en": evento.ocurrido_en.isoformat(),
        }
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: productor.send(json.dumps(mensaje).encode())
        )

    def cerrar(self) -> None:
        if self._cliente is not None:
            self._cliente.close()
