"""Eventos de DOMINIO del agregado `Pago` — internos al microservicio Pagos,
delgados, nunca cruzan a un broker directamente (este servicio no tiene
tópico de integración propio, ver README.md sección "Eventos: dominio vs.
integración"). Existen para que
`application/dispatcher_eventos_dominio.py` tenga algo que despachar y para
que las transiciones de estado de `Pago` queden trazadas como eventos
reales, no como simple asignación de atributo."""

from dataclasses import dataclass

from app.domain.pagos.value_objects import PagoId, TrabajoId
from app.domain.seedwork.domain_event import DomainEvent


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
