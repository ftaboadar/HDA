"""Evento de DOMINIO: interno al servicio, nunca cruza a un broker externo
directamente (eso es un evento de INTEGRACIÓN — ver
app/application/dispatcher_eventos_dominio.py y la clasificación completa en
11-implementacion-ddd-verificacion.md, sección 5). Un handler de aplicación
puede decidir, como reacción a un evento de dominio, publicar un evento de
integración — pero son dos conceptos distintos, no el mismo objeto viajando
más lejos."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class DomainEvent:
    # kw_only: así las subclases pueden agregar campos obligatorios sin
    # violar el orden de dataclasses (campos con default no pueden preceder
    # a campos sin default en la lista posicional).
    event_id: uuid.UUID = field(default_factory=uuid.uuid4, kw_only=True)
    ocurrido_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc), kw_only=True)

    @property
    def tipo(self) -> str:
        return type(self).__name__
