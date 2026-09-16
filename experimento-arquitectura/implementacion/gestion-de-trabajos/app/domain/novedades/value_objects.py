"""Value Objects del agregado `Novedad` — mismo patrón que
`domain/trabajo/value_objects.py`: dataclasses `frozen=True`, validación en
`__post_init__`/`__init__`, igualdad por valor. `Novedad` reutiliza
`TrabajoId` de `domain/trabajo/value_objects.py` directamente (no copia) —
préstamo válido porque `Novedad` y `Trabajo` viven en el mismo Bounded
Context (Gestión de Trabajos, ver 03-contextos-acotados-TO-BE.cml); no es
el mismo caso que la separación de Pagos en otro proceso, donde sí hizo
falta duplicar VOs (ver docstring de ese archivo)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from app.domain.seedwork.value_object import ValueObject


@dataclass(frozen=True)
class NovedadId(ValueObject):
    valor: uuid.UUID

    @staticmethod
    def nueva() -> NovedadId:
        return NovedadId(uuid.uuid4())

    @staticmethod
    def desde_str(valor: str) -> NovedadId:
        return NovedadId(uuid.UUID(valor))

    def __str__(self) -> str:
        return str(self.valor)


class EstadoNovedad(str, Enum):
    """PENDIENTE: creada, en cola o en proceso de envío hacia el CRM.
    ENTREGADA: el CRM confirmó la recepción del webhook.
    AGOTADA: se agotaron los reintentos configurados
    (`settings.throttler_max_reintentos`) sin lograr una entrega exitosa —
    la novedad NO se pierde en silencio: queda persistida en este estado
    para que otro proceso (fuera del alcance de este skeleton, ver
    README.md "Qué falta") pueda revisarla o reintentarla manualmente."""

    PENDIENTE = "PENDIENTE"
    ENTREGADA = "ENTREGADA"
    AGOTADA = "AGOTADA"
