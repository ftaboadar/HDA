"""Eventos de DOMINIO propios de Reputación -- el estado del agregado
`PerfilReputacion` se reconstruye reproduciendo esta lista (Event Sourcing,
ver perfil_reputacion.py). Persistidos en la tabla `eventos_reputacion`
(ver infrastructure/persistence/event_store_sqlalchemy.py).

Estos eventos NUNCA cruzan a Pulsar -- son el registro de hechos internos
del agregado, no eventos de integración. Distintos del evento de
INTEGRACIÓN `trabajos.finalizado` que SÍ llega por Pulsar desde Gestión de
Trabajos (ver infrastructure/messaging/consumidor_pulsar.py) -- ese es
tráfico de ENTRADA al proceso, nunca se modela como un DomainEvent de este
módulo (ver docstring de domain/seedwork/domain_event.py)."""

from dataclasses import dataclass

from app.domain.reputacion.value_objects import Garantia, ProveedorId, TrabajoId
from app.domain.seedwork.domain_event import DomainEvent


@dataclass(frozen=True)
class ProveedorCalificado(DomainEvent):
    proveedor_id: ProveedorId
    trabajo_id: TrabajoId
    puntaje: int
    comentario: str | None = None
    garantia: Garantia | None = None
