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

Se unifica al mismo contrato que ya usa `proveedores/app/common/publicador.py`
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
import time
from typing import Any

from app.application.ports.publicador import IPublicador
from app.common.config import settings
from app.common.logging_utils import (
    configurar_logging,
    describir_mensaje,
    log_evento,
)
from app.domain.ciclo_vida.eventos import TrabajoFinalizado


logger = configurar_logging("infrastructure.messaging.publicador_pulsar")

# Versión del contrato JSON del evento `trabajos.finalizado`. Viaja como
# PROPIEDAD del mensaje Pulsar (metadata), no dentro del cuerpo: los
# consumidores actuales (json.loads + acceso por clave) toleran campos
# nuevos, así que evolucionar el contrato de forma aditiva no rompe a nadie.
VERSION_ESQUEMA = "1"


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
        # implementacion/proveedores/app/common/publicador.py con aio_pika /
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
        propiedades = {
            "tipo_evento": "TrabajoFinalizado",
            "version_esquema": VERSION_ESQUEMA,
            "content_type": "application/json",
            "productor": "gestion-de-trabajos",
        }
        inicio = time.perf_counter()
        loop = asyncio.get_event_loop()
        message_id = await loop.run_in_executor(
            None,
            lambda: productor.send(
                json.dumps(mensaje).encode(), properties=propiedades
            ),
        )
        log_evento(
            logger,
            "mensaje_publicado",
            detalle=True,
            **describir_mensaje(
                mensaje,
                canal="pulsar",
                topico=self._topic,
                version_esquema=VERSION_ESQUEMA,
            ),
            tipo_evento="TrabajoFinalizado",
            message_id=str(message_id),
            propiedades_mensaje=propiedades,
            clave_particion=None,
            duracion_publicacion_ms=round((time.perf_counter() - inicio) * 1000, 1),
        )

    async def publicar_comando(self, comando: Any) -> None:
        """Publica un ComandoSaga en el tópico correspondiente."""
        productor = self._asegurar_productor()
        
        # Mapeo simple de tipo de comando a tópico (solo para esta prueba)
        tipo = type(comando).__name__
        topic = self._topic # por defecto
        if tipo == "PublicarElegibles":
            topic = "hda/proveedores/elegibles"
        elif tipo == "ReservarFranja":
            topic = "hda/proveedores/franja.reservar"
        elif tipo == "RetenerPago":
            topic = "hda/pagos/pago.retener"
        elif tipo == "LiberarPago":
            topic = "hda/pagos/pago.liberar"
        elif tipo == "LiberarFranja":
            topic = "hda/proveedores/franja.liberar"
        elif tipo == "CompensarPago":
            topic = "hda/pagos/pago.compensar"
            
        import dataclasses
        if dataclasses.is_dataclass(comando):
            mensaje = dataclasses.asdict(comando)
        else:
            mensaje = vars(comando)
            
        propiedades = {
            "tipo_evento": tipo,
            "version_esquema": "1",
            "content_type": "application/json",
            "productor": "gestion-de-trabajos",
        }
        
        loop = asyncio.get_event_loop()
        import pulsar
        cliente = pulsar.Client(self._service_url)
        prod = cliente.create_producer(topic)
        try:
            await loop.run_in_executor(
                None,
                lambda: prod.send(
                    json.dumps(mensaje).encode(), properties=propiedades
                ),
            )
        finally:
            cliente.close()

    def cerrar(self) -> None:
        if self._cliente is not None:
            self._cliente.close()
