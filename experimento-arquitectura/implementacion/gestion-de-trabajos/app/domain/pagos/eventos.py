"""Eventos de DOMINIO del agregado `Pago` — mismo principio que
`domain/trabajo/eventos.py`: internos, delgados, nunca cruzan a Pulsar
directamente (Pagos no tiene tópico propio, ver
`app/application/ports/publicador.py`). Antes de este archivo, `Pago` no
registraba ningún evento — sus transiciones de estado quedaban como simple
asignación de atributo, sin trazabilidad como evento real. Existen para que
`application/dispatcher_eventos_dominio.py` tenga algo que despachar desde
este agregado también, no solo desde `Trabajo`."""

from dataclasses import dataclass

from app.domain.pagos.value_objects import PagoId
from app.domain.seedwork.domain_event import DomainEvent
from app.domain.trabajo.value_objects import TrabajoId


@dataclass(frozen=True)
class PagoMarcadoExitoso(DomainEvent):
    pago_id: PagoId
    trabajo_id: TrabajoId
    referencia_externa: str


@dataclass(frozen=True)
class PagoMarcadoFallido(DomainEvent):
    pago_id: PagoId
    trabajo_id: TrabajoId
    motivo: str


@dataclass(frozen=True)
class PagoCompensado(DomainEvent):
    pago_id: PagoId
    trabajo_id: TrabajoId
