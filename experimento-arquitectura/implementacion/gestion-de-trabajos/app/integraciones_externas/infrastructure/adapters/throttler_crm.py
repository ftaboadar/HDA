"""Adaptador HTTP concreto de `IGestionAgentesPort`
(`application/ports/gestion_agentes.py`) hacia el mock del CRM SaaS "Gestión
de Agentes" — mismo patrón que
`pagos/app/infrastructure/adapters/pasarela_stripe.py`: URL configurable
(`settings.crm_mock_url`), import perezoso de `httpx` (así `domain/` y
`application/` no necesitan tenerlo instalado para poder importarse en un
test), sin tumbar el proceso si el mock no responde.

Responsabilidad deliberadamente acotada: este adaptador es transporte puro.
Detecta `429` (rate limit del CRM) y reporta el header `Retry-After` en
`ResultadoEnvioWebhook.reintentar_despues_s` — pero NO reintenta por su
cuenta ni conoce el token bucket. La política de reintento/backoff vive en
`infrastructure/messaging/throttler.py` (el Sidecar), que es quien decide
qué hacer con este resultado. Separar las dos cosas es lo que permite
probar el adaptador HTTP (con un mock de `httpx`) sin arrastrar la lógica
de colas/reintentos, y viceversa."""

from __future__ import annotations

from app.integraciones_externas.application.ports.gestion_agentes import (
    IGestionAgentesPort,
    ResultadoEnvioWebhook,
)
from app.common.config import settings
from app.novedades.domain.novedad import Novedad


class AdaptadorGestionAgentesHttp(IGestionAgentesPort):
    def __init__(self, base_url: str | None = None, timeout_s: float = 5.0) -> None:
        self._base_url = base_url or settings.crm_mock_url
        self._timeout_s = timeout_s

    async def enviar_webhook(self, novedad: Novedad) -> ResultadoEnvioWebhook:
        import time

        import httpx

        payload = {
            "novedad_id": str(novedad.id),
            "trabajo_id": str(novedad.trabajo_id),
            "descripcion": novedad.descripcion,
            "intentos": novedad.intentos,
        }
        inicio = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as cliente:
                respuesta = await cliente.post(
                    f"{self._base_url}/webhooks", json=payload
                )
                duracion_ms = round((time.perf_counter() - inicio) * 1000, 1)

                if respuesta.status_code == 429:
                    return ResultadoEnvioWebhook(
                        exitoso=False,
                        motivo_falla="rate_limited_429",
                        reintentar_despues_s=_parsear_retry_after(
                            respuesta.headers.get("Retry-After")
                        ),
                        status_http=429,
                        duracion_ms=duracion_ms,
                    )

                respuesta.raise_for_status()
                return ResultadoEnvioWebhook(
                    exitoso=True,
                    status_http=respuesta.status_code,
                    duracion_ms=duracion_ms,
                )
        except httpx.HTTPError as exc:
            # Error transitorio (timeout, conexión rechazada, 5xx vía
            # raise_for_status, etc.) — se reporta como fallo simple, sin
            # Retry-After; el Throttler calcula su propio backoff en este
            # caso (ver infrastructure/messaging/throttler.py).
            return ResultadoEnvioWebhook(
                exitoso=False,
                motivo_falla=str(exc),
                status_http=getattr(
                    getattr(exc, "response", None), "status_code", None
                ),
                duracion_ms=round((time.perf_counter() - inicio) * 1000, 1),
            )


def _parsear_retry_after(valor: str | None) -> float | None:
    """`Retry-After` (RFC 9110 §10.2.3) puede venir como segundos o como
    fecha HTTP — este mock/CRM de prueba solo necesita soportar el caso de
    segundos, que es el que produce el doble construido en
    `implementacion/mocks-crm/`; se documenta la limitación en vez de
    implementar el parseo de fecha sin un caso de uso real que lo ejercite."""
    if not valor:
        return None
    try:
        return float(valor)
    except ValueError:
        return None
