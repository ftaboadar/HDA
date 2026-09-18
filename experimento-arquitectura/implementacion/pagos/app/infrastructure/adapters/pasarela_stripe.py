"""Adapter (patrón) concreto de `IPasarelaDePago` hacia el mock de Stripe.

El mock real lo construye Johan en `implementacion/mocks-pagos/` (mismo
patrón que los dobles de Policía/RUES/CONTE en DISP-03: FastAPI + endpoint
de control de fallas/latencia) — este adaptador solo necesita una URL
configurable (`settings.stripe_mock_url`, default
`http://localhost:9100`), no bloquea el desarrollo de este servicio
mientras ese mock se termina en paralelo (12-plan-entrega-4.md, runbook de
Frans, sección "Coordinación")."""

from __future__ import annotations

from app.application.ports.pasarela_de_pago import IPasarelaDePago, ResultadoCobro
from app.common.config import settings
from app.domain.pagos.pago import Pago


class PasarelaStripe(IPasarelaDePago):
    def __init__(
        self, base_url: str | None = None, timeout_s: float | None = None
    ) -> None:
        self._base_url = base_url or settings.stripe_mock_url
        self._timeout_s = timeout_s or settings.http_timeout_s

    async def cobrar(self, pago: Pago) -> ResultadoCobro:
        import httpx

        payload = {
            "amount": str(pago.monto.valor),
            "currency": pago.monto.moneda,
            "metadata": {"pago_id": str(pago.id), "trabajo_id": str(pago.trabajo_id)},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as cliente:
                respuesta = await cliente.post(
                    f"{self._base_url}/v1/charges", json=payload
                )
                respuesta.raise_for_status()
                datos = respuesta.json()
                return ResultadoCobro(
                    exitoso=True, referencia_externa=datos.get("id", "")
                )
        except httpx.HTTPError as exc:
            return ResultadoCobro(exitoso=False, motivo_falla=str(exc))
