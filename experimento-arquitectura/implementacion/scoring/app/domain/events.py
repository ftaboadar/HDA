from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass
class DomainEvent:
    pass

@dataclass
class ScoringActualizadoEvent(DomainEvent):
    fotografo_id: UUID
    nueva_puntuacion: float
    fecha: datetime

class EventDispatcher:
    def __init__(self):
        self._handlers = {}

    def subscribe(self, event_type, handler):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def dispatch(self, event):
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            handler(event)
