"""Evento de DOMINIO: interno al servicio, nunca cruza a un broker (Pulsar)
directamente — eso es un evento de INTEGRACIÓN (ver
app/infrastructure/messaging/publicador_pulsar.py y la nota de la sección
4.0 de 12-plan-entrega-4.md). Un caso de uso de `application/` puede
decidir, como reacción a un evento de dominio, publicar un evento de
integración a través de un puerto — pero son dos conceptos distintos, no el
mismo objeto viajando más lejos.

Distinción explícita para este servicio (ver README.md, sección "Eventos:
dominio vs. integración"): `TrabajoFinalizado` en
`domain/trabajo/eventos.py` es el evento de dominio; el mensaje Avro que
`PublicadorPulsar` efectivamente pone en el tópico `trabajos.finalizado` es
el evento de integración correspondiente — comparten nombre por la
simplificación de skeleton descrita en 12-plan-entrega-4.md sección 3, no
porque sean el mismo objeto técnico."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class DomainEvent:
    # kw_only: así las subclases pueden agregar campos obligatorios sin
    # violar el orden de dataclasses (campos con default no pueden preceder
    # a campos sin default en la lista posicional).
    event_id: uuid.UUID = field(default_factory=uuid.uuid4, kw_only=True)
    ocurrido_en: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), kw_only=True
    )

    @property
    def tipo(self) -> str:
        return type(self).__name__
