from pydantic import BaseModel


class TrabajoFinalizadoPayload(BaseModel):
    cliente_id: str
    trabajo_id: str
    exito: bool


class ScoringActualizadoPayload(BaseModel):
    cliente_id: str
    nuevo_puntaje: int
