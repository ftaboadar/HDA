"""Strategy `ReglaRegional` — patrón explícitamente pedido por
escenarios_calidad.md (MOD-02) y por 12-plan-entrega-4.md sección 0.1:
"Módulo de reglas regionales (patrón Strategy) dentro de Gestión de
Trabajos". Cada región tiene su propia implementación concreta en
`infrastructure/adapters/regla_*.py` — el dominio solo conoce esta
interfaz, nunca las implementaciones concretas ni ningún detalle de HTTP.

`validar` puede lanzar cualquier excepción de dominio (ej. `ValueError`) si
el pago no cumple una regla de esa región (ej. monto mínimo/máximo,
moneda esperada) — se ejecuta ANTES de llamar a la pasarela externa."""

from __future__ import annotations

import abc
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # evita import circular en tiempo de ejecución
    from app.domain.pagos.pago import Pago


class ReglaRegional(abc.ABC):
    @abc.abstractmethod
    def calcular_comision(self, monto: Decimal) -> Decimal:
        """Comisión que se retiene sobre el monto del trabajo antes de
        liquidar al proveedor — varía por región, de ahí el Strategy."""

    @abc.abstractmethod
    def validar(self, pago: Pago) -> None:
        """Lanza una excepción de dominio si `pago` no cumple las reglas de
        esta región. No retorna nada (comando, no query) — CQS: valida por
        efecto secundario (excepción), no por valor de retorno."""
