from dataclasses import dataclass
from datetime import datetime
import uuid

@dataclass
class DomainEvent:
    id: str = str(uuid.uuid4())
    timestamp: datetime = datetime.utcnow()

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
