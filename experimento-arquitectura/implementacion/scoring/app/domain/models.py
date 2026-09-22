from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4
from typing import List
from app.domain.events import DomainEvent, ScoringActualizadoEvent

@dataclass
class FotografoScoring:
    fotografo_id: UUID
    id: UUID = field(default_factory=uuid4)
    puntuacion_actual: float = 0.0
    trabajos_completados: int = 0
    fecha_ultima_actualizacion: datetime = field(default_factory=datetime.utcnow)
    _events: List[DomainEvent] = field(default_factory=list)

    def registrar_trabajo_finalizado(self, calificacion_trabajo: float):
        total_puntuacion = (self.puntuacion_actual * self.trabajos_completados) + calificacion_trabajo
        self.trabajos_completados += 1
        self.puntuacion_actual = total_puntuacion / self.trabajos_completados
        self.fecha_ultima_actualizacion = datetime.utcnow()
        
        self._events.append(
            ScoringActualizadoEvent(
                fotografo_id=self.fotografo_id,
                nueva_puntuacion=self.puntuacion_actual,
                fecha=self.fecha_ultima_actualizacion
            )
        )

    def clear_events(self):
        self._events.clear()
