import uuid
from datetime import datetime, timezone
from app.domain.seedwork.aggregate_root import AggregateRoot
from app.domain.workflow.value_objects import EstadoSaga, PasoSaga
from app.domain.ciclo_vida.value_objects import TrabajoId

class SagaInstancia(AggregateRoot):
    def __init__(
        self,
        id: uuid.UUID,
        trabajo_id: TrabajoId,
        origen: str,
        estado: EstadoSaga = EstadoSaga.INICIADA,
        paso_actual: PasoSaga = PasoSaga.CREAR_TRABAJO,
        iniciada_en: datetime | None = None,
        actualizada_en: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self.trabajo_id = trabajo_id
        self.origen = origen
        self.estado = estado
        self.paso_actual = paso_actual
        self.iniciada_en = iniciada_en or datetime.now(timezone.utc)
        self.actualizada_en = actualizada_en or datetime.now(timezone.utc)

    def avanzar_paso(self, nuevo_paso: PasoSaga) -> None:
        self.paso_actual = nuevo_paso
        self.actualizada_en = datetime.now(timezone.utc)

    def completar(self) -> None:
        self.estado = EstadoSaga.COMPLETADA
        self.actualizada_en = datetime.now(timezone.utc)

    def compensar(self) -> None:
        self.estado = EstadoSaga.COMPENSADA
        self.actualizada_en = datetime.now(timezone.utc)

