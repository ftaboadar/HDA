"""Value Objects propios del microservicio Pagos.

Hasta la separación de este servicio, `Dinero`/`Region` se reutilizaban desde
`domain/trabajo/value_objects.py` de Gestión de Trabajos (ver
`12-plan-entrega-4.md` sección 0.1, donde Pagos era un submódulo ACL dentro
de ese mismo proceso) y el propio docstring de ese archivo ya anticipaba:
"serían Value Objects propios si Pagos fuera otro microservicio". Ahora que
Pagos es un microservicio independiente, esa condición se cumple: `Dinero`,
`Region` y `TrabajoId` son copias locales, sin ningún import hacia
`gestion-de-trabajos` (dos procesos separados no comparten código de
dominio — cada Bounded Context es dueño de su propio vocabulario, mismo
principio que ya aplicaba `domain/seedwork/entity.py` sobre no compartir
seedwork entre servicios).

`TrabajoId` aquí es solo una referencia por id al agregado `Trabajo` de
OTRO microservicio (Gestión de Trabajos) — Pagos nunca importa su modelo,
solo conoce este id, igual que `ProveedorId` en Gestión de Trabajos
referencia al agregado `Proveedor` de otro Bounded Context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.domain.seedwork.value_object import ValueObject


@dataclass(frozen=True)
class TrabajoId(ValueObject):
    """Referencia por id al agregado `Trabajo` de Gestión de Trabajos (otro
    microservicio) — Pagos aprende de su existencia únicamente a través del
    body de `POST /pagos` (ver README.md de este servicio, sección
    "Frontera del API"), nunca por llamada directa ni por compartir
    modelo/BD con ese servicio."""

    valor: uuid.UUID

    @staticmethod
    def nueva() -> TrabajoId:
        return TrabajoId(uuid.uuid4())

    @staticmethod
    def desde_str(valor: str) -> TrabajoId:
        return TrabajoId(uuid.UUID(valor))

    def __str__(self) -> str:
        return str(self.valor)


class Region(str, Enum):
    """Copia local de `gestion-de-trabajos/app/domain/trabajo/value_objects.Region`
    — mismos valores, extensible igual (MOD-02): agregar una región nueva
    implica agregar un valor aquí + una nueva `ReglaRegional` en
    `infrastructure/adapters/`, sin tocar las reglas existentes."""

    COLOMBIA = "CO"
    BRASIL = "BR"


@dataclass(frozen=True)
class ProveedorId(ValueObject):
    """Copia local de `gestion-de-trabajos/app/domain/trabajo/value_objects.ProveedorId`
    — referencia por id al agregado `Proveedor` de OTRO Bounded Context;
    Pagos nunca importa su modelo, solo conoce este id. Usado únicamente por
    `RegistroTrabajoElegible` (application/ports/registro_trabajos.py)."""

    valor: str

    def __post_init__(self) -> None:
        if not self.valor:
            raise ValueError("ProveedorId no puede estar vacío")

    def __str__(self) -> str:
        return self.valor


@dataclass(frozen=True)
class Dinero(ValueObject):
    """Copia local de `gestion-de-trabajos/app/domain/trabajo/value_objects.Dinero`
    — mismo comportamiento y campos, sin import cruzado entre
    microservicios."""

    valor: Decimal
    moneda: str = "COP"

    def __post_init__(self) -> None:
        if self.valor <= 0:
            raise ValueError("Dinero.valor debe ser positivo")
        if not self.moneda:
            raise ValueError("Dinero.moneda no puede estar vacía")

    def __str__(self) -> str:
        return f"{self.valor} {self.moneda}"


@dataclass(frozen=True)
class PagoId(ValueObject):
    valor: uuid.UUID

    @staticmethod
    def nueva() -> PagoId:
        return PagoId(uuid.uuid4())

    @staticmethod
    def desde_str(valor: str) -> PagoId:
        return PagoId(uuid.UUID(valor))

    def __str__(self) -> str:
        return str(self.valor)


class Pasarela(str, Enum):
    """Adapter (patrón, ver domain/pagos/pago.py y
    infrastructure/adapters/pasarela_*.py) — agregar una pasarela nueva
    (MOD-02) implica agregar un valor aquí + un adaptador concreto de
    `IPasarelaDePago`, sin tocar los existentes."""

    STRIPE = "stripe"
    MERCADOPAGO = "mercadopago"


class EstadoPago(str, Enum):
    PENDIENTE = "PENDIENTE"
    EXITOSO = "EXITOSO"
    FALLIDO = "FALLIDO"
    COMPENSADO = "COMPENSADO"
