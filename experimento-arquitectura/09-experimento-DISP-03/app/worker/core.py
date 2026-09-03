"""Lógica de procesamiento de una verificación — agnóstica de transporte.

Tácticas implementadas aquí (ver plan.md, sección 4): timeout por llamada,
reintentos con backoff exponencial + jitter, número de intentos acotado.
La usan tanto el consumidor pull de RabbitMQ (worker/main.py, local) como el
handler push de Pub/Sub (worker/push_handler.py, GCP) — es la evidencia de que
la táctica de resiliencia en sí es portable, aunque el transporte que la
invoca no sea idéntico entre ambos entornos."""
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.common.config import settings
from app.common.logging_utils import configurar_logging, log_evento

logger = configurar_logging("worker.core")


class FallaExterna(Exception):
    pass


@dataclass
class ResultadoProceso:
    exito: bool
    intentos: int
    motivo_falla: Optional[str] = None


def _url_externa(tipo_verificador: str) -> str:
    return {
        "policia": settings.mock_policia_url,
        "rues": settings.mock_rues_url,
        "certificadora": settings.mock_certificadora_url,
    }[tipo_verificador]


async def _llamar_externo(tipo_verificador: str, proveedor_id: str) -> None:
    url = f"{_url_externa(tipo_verificador)}/verificar"
    async with httpx.AsyncClient(timeout=settings.timeout_externo_s) as cliente:
        resp = await cliente.post(url, json={"proveedor_id": proveedor_id})
    if resp.status_code >= 500:
        raise FallaExterna(f"HTTP {resp.status_code} de {tipo_verificador}")
    resp.raise_for_status()


async def procesar_verificacion(
    verificacion_id: str, proveedor_id: str, tipo_verificador: str
) -> ResultadoProceso:
    intentos = 0
    ultimo_error: Optional[str] = None

    @retry(
        reraise=True,
        stop=stop_after_attempt(settings.max_reintentos),
        wait=wait_exponential_jitter(
            initial=settings.backoff_base_s, max=settings.backoff_max_s
        ),
        retry=retry_if_exception_type(
            (FallaExterna, httpx.TransportError, httpx.TimeoutException)
        ),
    )
    async def _intentar():
        nonlocal intentos, ultimo_error
        intentos += 1
        inicio = time.time()
        try:
            await _llamar_externo(tipo_verificador, proveedor_id)
            log_evento(
                logger,
                "verificacion_intento_exitoso",
                verificacion_id=verificacion_id,
                tipo_verificador=tipo_verificador,
                intento=intentos,
                duracion_ms=int((time.time() - inicio) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 — se reclasifica y se re-lanza intencionalmente
            ultimo_error = str(exc)
            log_evento(
                logger,
                "verificacion_intento_fallido",
                verificacion_id=verificacion_id,
                tipo_verificador=tipo_verificador,
                intento=intentos,
                error=ultimo_error,
                duracion_ms=int((time.time() - inicio) * 1000),
            )
            raise

    try:
        await _intentar()
        return ResultadoProceso(exito=True, intentos=intentos)
    except Exception:  # noqa: BLE001 — reintentos agotados, se captura para enrutar a DLQ
        log_evento(
            logger,
            "verificacion_reintentos_agotados",
            verificacion_id=verificacion_id,
            tipo_verificador=tipo_verificador,
            intentos=intentos,
            motivo_falla=ultimo_error,
        )
        return ResultadoProceso(exito=False, intentos=intentos, motivo_falla=ultimo_error)
