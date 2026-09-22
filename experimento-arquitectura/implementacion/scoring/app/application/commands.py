from dataclasses import dataclass
from uuid import UUID

@dataclass
class ActualizarScoringCommand:
    fotografo_id: UUID
    calificacion: float
