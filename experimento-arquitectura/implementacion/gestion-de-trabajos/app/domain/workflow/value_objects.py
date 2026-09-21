from __future__ import annotations
import uuid
from dataclasses import dataclass
from enum import Enum
from app.domain.seedwork.value_object import ValueObject

@dataclass(frozen=True)
class SagaId(ValueObject):
    valor: uuid.UUID
    
    @staticmethod
    def nueva() -> SagaId:
        return SagaId(uuid.uuid4())
        
    def __str__(self) -> str:
        return str(self.valor)

class EstadoSaga(str, Enum):
    INICIADA = "INICIADA"
    COMPLETADA = "COMPLETADA"
    COMPENSADA = "COMPENSADA"

class PasoSaga(str, Enum):
    CREAR_TRABAJO = "CREAR_TRABAJO"
    PUBLICAR_ELEGIBLES = "PUBLICAR_ELEGIBLES"
    RESERVAR_FRANJA = "RESERVAR_FRANJA"
    RETENER_PAGO = "RETENER_PAGO"
    INICIAR_WORKFLOW = "INICIAR_WORKFLOW"
    LIBERAR_PAGO = "LIBERAR_PAGO"
    FACTURAR_PARTNER = "FACTURAR_PARTNER"
    LIBERAR_FRANJA = "LIBERAR_FRANJA"
    COMPENSAR_PAGO = "COMPENSAR_PAGO"

