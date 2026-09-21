from dataclasses import dataclass
from enum import Enum
from app.seedwork.value_object import ValueObject

class TipoBloqueFranja(Enum):
    MANANA = "MANANA"
    TARDE = "TARDE"

@dataclass(frozen=True)
class Franja(ValueObject):
    dia_semana: int # 0=Lunes, ..., 6=Domingo
    bloque: TipoBloqueFranja
