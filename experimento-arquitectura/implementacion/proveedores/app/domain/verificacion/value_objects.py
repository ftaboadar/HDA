"""Value Objects del agregado Verificacion — inmutables, con validación en
el constructor, igualdad por valor. Distintos (a propósito) de los `Literal`
de app/common/schemas.py: esos son el contrato de serialización HTTP, estos
son el vocabulario del dominio — no se mezclan capas."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from app.domain.seedwork.value_object import ValueObject


@dataclass(frozen=True)
class VerificacionId(ValueObject):
    valor: uuid.UUID

    @staticmethod
    def nueva() -> VerificacionId:
        return VerificacionId(uuid.uuid4())

    @staticmethod
    def desde_str(valor: str) -> VerificacionId:
        return VerificacionId(uuid.UUID(valor))

    def __str__(self) -> str:
        return str(self.valor)


@dataclass(frozen=True)
class ProveedorId(ValueObject):
    valor: str

    def __post_init__(self) -> None:
        if not self.valor:
            raise ValueError("ProveedorId no puede estar vacío")

    def __str__(self) -> str:
        return self.valor


class TipoVerificador(str, Enum):
    POLICIA = "policia"
    RUES = "rues"
    CERTIFICADORA = "certificadora"


class EstadoVerificacion(str, Enum):
    PENDIENTE = "PENDIENTE"
    COMPLETADA = "COMPLETADA"
    FALLIDA_DLQ = "FALLIDA_DLQ"


class ResultadoIntento(str, Enum):
    EXITOSO = "EXITOSO"
    FALLIDO = "FALLIDO"


class NivelVerificacion(str, Enum):
    """Qué nivel de habilitación otorga una Verificacion aprobada — ver
    enunciado: "una verificación/auditoría básica habilita el marketplace;
    el proceso de verificación completo... habilita claims e instalaciones"."""

    BASICA = "BASICA"
    COMPLETA = "COMPLETA"


class MotivoRevalidacion(str, Enum):
    VENCIMIENTO_CERTIFICADO = "VENCIMIENTO_CERTIFICADO"
    TECNICO_NUEVO = "TECNICO_NUEVO"
    PROGRAMADA = "PROGRAMADA"
