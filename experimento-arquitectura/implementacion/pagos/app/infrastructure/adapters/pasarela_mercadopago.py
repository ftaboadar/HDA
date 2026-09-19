"""Adapter (patrón) concreto de `IPasarelaDePago` hacia el mock de
MercadoPago — agregado sin tocar `PasarelaStripe` (MOD-02, ver
README.md)."""

from __future__ import annotations

from app.application.ports.pasarela_de_pago import IPasarelaDePago, ResultadoCobro
from app.common.config import settings
from app.common.logging_utils import (
    configurar_logging,
    headers_trace_salientes,
    log_evento,
)
from app.domain.pagos.pago import Pago


logger = configurar_logging("infrastructure.adapters.pasarela_mercadopago")


class PasarelaMercadoPago(IPasarelaDePago):
    def __init__(
        self, base_url: str | None = None, timeout_s: float | None = None
    ) -> None:
        self._base_url = base_url or settings.mercadopago_mock_url
        self._timeout_s = timeout_s or settings.http_timeout_s

    async def cobrar(self, pago: Pago) -> ResultadoCobro:
        import time

        import httpx

        payload = {
            "transaction_amount": float(pago.monto.valor),
            "currency_id": pago.monto.moneda,
            "external_reference": str(pago.id),
            "description": f"trabajo:{pago.trabajo_id}",
        }
        log_evento(
            logger,
            "pasarela_cobro_solicitado",
            sistema_externo="mercadopago",
            pago_id=str(pago.id),
            endpoint="/v1/payments",
            monto_enviado=payload["transaction_amount"],
            unidad_monto="unidades_decimal",
            monto_dominio=str(pago.monto.valor),
            moneda=pago.monto.moneda,
        )
        inicio = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as cliente:
                respuesta = await cliente.post(
                    f"{self._base_url}/v1/payments",
                    json=payload,
                    headers=headers_trace_salientes(),
                )
                respuesta.raise_for_status()
                datos = respuesta.json()
                log_evento(
                    logger,
                    "pasarela_cobro_respuesta",
                    sistema_externo="mercadopago",
                    pago_id=str(pago.id),
                    status_http=getattr(respuesta, "status_code", None),
                    referencia_externa=str(datos.get("id", "")),
                    duracion_pasarela_ms=round(
                        (time.perf_counter() - inicio) * 1000, 1
                    ),
                )
                return ResultadoCobro(
                    exitoso=True, referencia_externa=str(datos.get("id", ""))
                )
        except httpx.HTTPError as exc:
            log_evento(
                logger,
                "pasarela_cobro_fallido",
                nivel="error",
                sistema_externo="mercadopago",
                pago_id=str(pago.id),
                error=str(exc),
                duracion_pasarela_ms=round((time.perf_counter() - inicio) * 1000, 1),
            )
            return ResultadoCobro(exitoso=False, motivo_falla=str(exc))
