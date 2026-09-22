"""Base de Aggregate Root: extiende Entity y acumula eventos de dominio
pendientes de despacho. El application layer los recoge después de guardar
el agregado (ver app/ciclo_suscripcion/application/commands/) — el agregado
nunca despacha ni publica sus propios eventos, solo los produce.

Contrato: `add_event(evento)` (producer, llamado desde los métodos de
negocio del agregado), `eventos` (lectura del buffer pendiente) y
`clear_events()` (limpia el buffer, se llama una sola vez justo después de
persistir el agregado y despachar los eventos) — nombres alineados con los
call sites reales en app/ciclo_suscripcion/application/commands/*.py."""

from __future__ import annotations

import uuid

from app.seedwork.domain_event import DomainEvent
from app.seedwork.entity import Entity


class AggregateRoot(Entity):
    def __init__(self, id: uuid.UUID) -> None:
        super().__init__(id)
        self._eventos_dominio: list[DomainEvent] = []

    @property
    def eventos(self) -> list[DomainEvent]:
        return list(self._eventos_dominio)

    def add_event(self, evento: DomainEvent) -> None:
        self._eventos_dominio.append(evento)

    def clear_events(self) -> None:
        self._eventos_dominio = []
