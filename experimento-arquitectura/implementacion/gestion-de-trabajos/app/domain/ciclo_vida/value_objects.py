"""Value Objects del agregado `Trabajo` — inmutables, con validación en el
constructor, igualdad por valor. Distintos (a propósito) de los schemas de
`app/common/schemas.py`: esos son el contrato de serialización HTTP, estos
son el vocabulario del dominio — no se mezclan capas.

Separación de Pagos: hasta que ese módulo era un submódulo ACL de este
mismo proceso, `Dinero` y `Region` se reutilizaban también desde
`domain/pagos/` — préstamo válido *dentro del mismo Bounded Context*. Ahora
que Pagos es un microservicio independiente
(`implementacion/pagos/README.md`), tiene sus propias copias locales de
estos VOs (`implementacion/pagos/app/domain/pagos/value_objects.py`); no
hay ningún import cruzado entre los dos servicios."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.domain.seedwork.value_object import ValueObject


@dataclass(frozen=True)
class TrabajoId(ValueObject):
    valor: uuid.UUID

    @staticmethod
    def nueva() -> TrabajoId:
        return TrabajoId(uuid.uuid4())

    @staticmethod
    def desde_str(valor: str) -> TrabajoId:
        return TrabajoId(uuid.UUID(valor))

    def __str__(self) -> str:
        return str(self.valor)


@dataclass(frozen=True)
class ProveedorId(ValueObject):
    """Referencia por id al agregado `Proveedor` de OTRO Bounded Context
    (ver 07-vista-informacion.puml: "referencias entre agregados de
    distintos módulos son solo por id, sin composición"). Gestión de
    Trabajos nunca importa el modelo de Proveedores — solo conoce este id."""

    valor: str

    def __post_init__(self) -> None:
        if not self.valor:
            raise ValueError("ProveedorId no puede estar vacío")

    def __str__(self) -> str:
        return self.valor


class Region(str, Enum):
    """Extensible a propósito (MOD-02, ver 12-plan-entrega-4.md sección 1):
    agregar una región nueva implica agregar un valor aquí + una nueva
    `ReglaRegional` en infrastructure/adapters/ — nunca tocar las reglas ya
    existentes."""

    COLOMBIA = "CO"
    BRASIL = "BR"


# Moneda por defecto de cada región — vive aquí (no en infraestructura)
# porque es una regla de negocio estable (qué moneda usa cada región), no un
# detalle técnico; distinto de la comisión, que sí es una Strategy porque
# varía y se espera que crezca (ver domain/pagos/regla_regional.py).
MONEDA_POR_REGION: dict[Region, str] = {
    Region.COLOMBIA: "COP",
    Region.BRASIL: "BRL",
}


class EstadoTrabajo(str, Enum):
    """Skeleton simplificado (ver 12-plan-entrega-4.md sección 3): no se
    modelan los estados intermedios del ciclo de vida real de un Trabajo
    (ASIGNADO, EN_PROGRESO, etc. — ver SubTrabajo/Cotizacion en
    07-vista-informacion.puml) — eso es parte de la Saga, Entrega 5."""

    SOLICITADO = "SOLICITADO"
    ESPERANDO_ELEGIBLES = "ESPERANDO_ELEGIBLES"
    ASIGNADO = "ASIGNADO"
    EN_CURSO = "EN_CURSO"
    FINALIZADO = "FINALIZADO"
    PAGADO = "PAGADO"
    EN_DISPUTA = "EN_DISPUTA"
    CANCELADO = "CANCELADO"


@dataclass(frozen=True)
class Dinero(ValueObject):
    valor: Decimal
    moneda: str = "COP"

    def __post_init__(self) -> None:
        if self.valor <= 0:
            raise ValueError("Dinero.valor debe ser positivo")
        if not self.moneda:
            raise ValueError("Dinero.moneda no puede estar vacía")

    def __str__(self) -> str:
        return f"{self.valor} {self.moneda}"
