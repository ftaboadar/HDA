"""Implementación concreta de `ReglaRegional` para Brasil — agregada sin
tocar `ReglaColombia` (MOD-02, ver README.md). Comisión más alta que
Colombia a propósito, para que el escenario de modificabilidad tenga algo
observable que comparar entre ambas reglas."""

from decimal import ROUND_HALF_UP, Decimal

from app.domain.pagos.pago import Pago
from app.domain.pagos.regla_regional import ReglaRegional

COMISION_BRASIL = Decimal("0.039")  # 3.9%, ilustrativo
MONTO_MAXIMO_BRL = Decimal(100000)  # 100 mil BRL, ilustrativo


class ReglaBrasil(ReglaRegional):
    def calcular_comision(self, monto: Decimal) -> Decimal:
        return (monto * COMISION_BRASIL).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def validar(self, pago: Pago) -> None:
        if pago.monto.moneda != "BRL":
            raise ValueError(
                f"ReglaBrasil espera moneda BRL, recibió {pago.monto.moneda}"
            )
        if pago.monto.valor > MONTO_MAXIMO_BRL:
            raise ValueError(
                f"Monto {pago.monto.valor} supera el máximo permitido en Brasil "
                f"({MONTO_MAXIMO_BRL})"
            )
