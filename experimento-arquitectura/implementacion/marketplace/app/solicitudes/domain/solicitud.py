from dataclasses import dataclass, field
import uuid
from typing import List
from .eventos import SolicitudCreada, EventoDominio

@dataclass
class Solicitud:
    cliente_id: str
    detalles: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    estado: str = "CREADA"
    eventos: List[EventoDominio] = field(default_factory=list)

    def crear(self):
        evento = SolicitudCreada(
            solicitud_id=self.id, 
            cliente_id=self.cliente_id, 
            detalles=self.detalles
        )
        self.eventos.append(evento)
