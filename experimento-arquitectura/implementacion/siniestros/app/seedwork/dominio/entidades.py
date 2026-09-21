import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field

@dataclass
class DomainEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ocurrido_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class Entity:
    def __init__(self, id: str):
        self.id = id

class AggregateRoot(Entity):
    def __init__(self, id: str):
        super().__init__(id)
        self.domain_events = []
    
    def add_domain_event(self, event: DomainEvent):
        self.domain_events.append(event)
