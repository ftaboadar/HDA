"""Adapter (patrón) concreto de `IPasarelaDePago` hacia el mock de
MercadoPago — agregado sin tocar `PasarelaStripe` (MOD-02, ver
README.md)."""

from __future__ import annotations

from app.application.ports.pasarela_de_pago import IPasarelaDePago, ResultadoCobro
from app.common.config import settings
from app.domain.pagos.pago import Pago


class PasarelaMercadoPago(IPasarelaDePago):
    def __init__(
        self, base_url: str | None = None, timeout_s: float | None = None
    ) -> None:
        self._base_url = base_url or settings.mercadopago_mock_url
        self._timeout_s = timeout_s or settings.http_timeout_s

    async def cobrar(self, pago: Pago) -> ResultadoCobro:
        import httpx

        payload = {
            "transaction_amount": float(pago.monto.valor),
            "currency_id": pago.monto.moneda,
            "external_reference": str(pago.id),
            "description": f"trabajo:{pago.trabajo_id}",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as cliente:
                respuesta = await cliente.post(
                    f"{self._base_url}/v1/payments", json=payload
                )
                respuesta.raise_for_status()
                datos = respuesta.json()
                return ResultadoCobro(
                    exitoso=True, referencia_externa=str(datos.get("id", ""))
                )
        except httpx.HTTPError as exc:
            return ResultadoCobro(exitoso=False, motivo_falla=str(exc))
