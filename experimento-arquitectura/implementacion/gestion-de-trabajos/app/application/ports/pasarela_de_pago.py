"""Puerto (Adapter, patrón) hacia el sistema externo Pagos — Stripe o
MercadoPago mockeados vía HTTP síncrono (ver 12-plan-entrega-4.md sección
0.1 y 3.1: "las únicas llamadas HTTP síncronas son hacia sistemas externos
mockeados", nunca entre microservicios propios). `application/commands`
programa contra esta interfaz; los adaptadores concretos viven en
`app/infrastructure/adapters/pasarela_stripe.py` y `pasarela_mercadopago.py`."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.pagos.pago import Pago


@dataclass(frozen=True)
class ResultadoCobro:
    """DTO de aplicación (no es un Value Object de dominio: vive en la
    frontera entre `application/` y el sistema externo)."""

    exitoso: bool
    referencia_externa: str | None = None
    motivo_falla: str | None = None


class IPasarelaDePago(abc.ABC):
    @abc.abstractmethod
    async def cobrar(self, pago: Pago) -> ResultadoCobro: ...
