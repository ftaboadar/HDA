from pydantic import BaseModel
import uuid
from typing import List


class EventoDominio(BaseModel):
    id: str
    tipo: str


class PerfilCrediticio(BaseModel):
    id: str
    cliente_id: str
    puntaje: int
    historial_trabajos: int
    eventos: List[EventoDominio] = []

    def registrar_trabajo_finalizado(self, exito: bool):
        if exito:
            self.puntaje += 10
        else:
            self.puntaje -= 5
        self.historial_trabajos += 1

        self.eventos.append(
            EventoDominio(id=str(uuid.uuid4()), tipo="ScoringActualizado")
        )
