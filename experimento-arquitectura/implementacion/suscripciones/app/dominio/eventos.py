from dataclasses import dataclass
from datetime import datetime

@dataclass
class EventoDominio:
    pass

@dataclass
class CargoRegistrado(EventoDominio):
    id_suscripcion: str
    id_cargo: str
    id_trabajo: str
    monto: float
    fecha: datetime
