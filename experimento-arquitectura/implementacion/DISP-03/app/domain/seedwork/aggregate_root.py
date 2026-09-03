"""Base de Aggregate Root: extiende Entity y acumula eventos de dominio
pendientes de despacho. El application layer los recoge después de guardar
el agregado (ver app/application/dispatcher_eventos_dominio.py) — el
agregado nunca despacha sus propios eventos, solo los produce."""

from __future__ import annotations

import uuid

from app.domain.seedwork.domain_event import DomainEvent
from app.domain.seedwork.entity import Entity


class AggregateRoot(Entity):
    def __init__(self, id: uuid.UUID) -> None:
        super().__init__(id)
        self._eventos_dominio: list[DomainEvent] = []

    def registrar_evento(self, evento: DomainEvent) -> None:
        self._eventos_dominio.append(evento)

    def recoger_eventos(self) -> list[DomainEvent]:
        """Devuelve los eventos acumulados y limpia el buffer — se llama una
        sola vez, justo después de persistir el agregado."""
        eventos, self._eventos_dominio = self._eventos_dominio, []
        return eventos
