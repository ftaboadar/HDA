from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass(kw_only=True)
class DomainEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class SiniestroAprobado(DomainEvent):
    siniestro_id: str
    monto_aprobado: float

@dataclass
class FacturacionProcesada(DomainEvent):
    siniestro_id: str
    factura_id: str
    monto: float

@dataclass
class CompensacionReservaRequerida(DomainEvent):
    siniestro_id: str
    monto_compensacion: float
    motivo: str
