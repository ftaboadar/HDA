"""Value Objects del submódulo ACL de Pagos — Pagos NO es un Bounded
Context propio (ver 12-plan-entrega-4.md sección 0.1: `Pagos` es
`GENERIC_SUBDOMAIN` externo en 01-dominios-subdominios.cml, sin
`BoundedContext` propio en 03-contextos-acotados-TO-BE.cml), por eso este
módulo vive dentro del mismo paquete `domain/` de Gestión de Trabajos y
puede reutilizar `Dinero`/`Region` de `domain/trabajo/value_objects.py` —
serían Value Objects propios si Pagos fuera otro microservicio."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from app.domain.seedwork.value_object import ValueObject


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
