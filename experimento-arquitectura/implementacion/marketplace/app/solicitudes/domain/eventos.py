import uuid
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class EventoDominio:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class SolicitudCreada(EventoDominio):
    solicitud_id: str = ""
    cliente_id: str = ""
    detalles: str = ""
