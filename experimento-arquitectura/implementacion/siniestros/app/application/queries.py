from dataclasses import dataclass
from typing import List

@dataclass
class GetSiniestroQuery:
    siniestro_id: str

@dataclass
class SiniestroDTO:
    id: str
    estado: str
    reserva: float
    facturas: List[dict]
