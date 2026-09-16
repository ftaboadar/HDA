"""Implementación concreta de `ReglaRegional` para Colombia (MOD-02: se
puede agregar/modificar esta regla sin tocar `ReglaBrasil` ni el core del
servicio). Valores de comisión y montos son ilustrativos para el PoC — no
son asesoría financiera real; quien complete el servicio debe validarlos
con negocio antes de producción."""

from decimal import ROUND_HALF_UP, Decimal

from app.domain.pagos.pago import Pago
from app.domain.pagos.regla_regional import ReglaRegional

COMISION_COLOMBIA = Decimal("0.029")  # 2.9%, ilustrativo
MONTO_MAXIMO_COP = Decimal(50000000)  # 50 millones COP, ilustrativo


class ReglaColombia(ReglaRegional):
    def calcular_comision(self, monto: Decimal) -> Decimal:
        return (monto * COMISION_COLOMBIA).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def validar(self, pago: Pago) -> None:
        if pago.monto.moneda != "COP":
            raise ValueError(
                f"ReglaColombia espera moneda COP, recibió {pago.monto.moneda}"
            )
        if pago.monto.valor > MONTO_MAXIMO_COP:
            raise ValueError(
                f"Monto {pago.monto.valor} supera el máximo permitido en Colombia "
                f"({MONTO_MAXIMO_COP})"
            )
