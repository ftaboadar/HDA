from dataclasses import dataclass
from datetime import datetime
from app.domain.seedwork.domain_event import DomainEvent

@dataclass(frozen=True)
class ComandoSaga(DomainEvent):
    """Representa un comando enviado como parte de la Saga."""
    comando_id: str
    saga_id: str
    correlation_id: str
    
@dataclass(frozen=True)
class PublicarElegibles(ComandoSaga):
    origen: str
    origen_id: str

@dataclass(frozen=True)
class ReservarFranja(ComandoSaga):
    proveedor_id: str
    tecnico_id: str
    fecha_franja: str
    bloque: str

@dataclass(frozen=True)
class RetenerPago(ComandoSaga):
    monto: float
    moneda: str

@dataclass(frozen=True)
class LiberarPago(ComandoSaga):
    pago_id: str

@dataclass(frozen=True)
class LiberarFranja(ComandoSaga):
    reserva_id: str

@dataclass(frozen=True)
class CompensarPago(ComandoSaga):
    pago_id: str

