from dataclasses import dataclass, field
from datetime import datetime
import uuid
from app.seedwork.domain_event import DomainEvent

@dataclass(kw_only=True)
class SuscripcionCreada(DomainEvent):
    id_evento: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    suscripcion_id: str
    cliente_id: str
    dia_semana: int
    bloque: str

@dataclass(kw_only=True)
class CicloSuscripcionGenerado(DomainEvent):
    id_evento: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    suscripcion_id: str
    ciclo_id: str
    proveedor_id: str | None
    es_primer_ciclo: bool
    dia_semana: int
    bloque: str

