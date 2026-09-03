"""Lógica de procesamiento de una verificación — agnóstica de transporte Y
(desde la capa DDD) agnóstica del sistema externo concreto: llama al puerto
`IVerificacionExternaPort`, resuelto por `infrastructure.config`, en vez de
`httpx` directo — cierra el segundo hueco de hexagonal (Regla 5, criterio 2).

Tácticas implementadas aquí (ver plan.md, sección 4): timeout por llamada
(dentro de cada adaptador concreto), reintentos con backoff exponencial +
jitter, número de intentos acotado — **sin cambios** respecto a la versión
anterior, solo cambió qué se llama (`puerto.verificar()` en vez de
`_llamar_externo()`), no cómo se reintenta.

La usan tanto el consumidor pull de RabbitMQ (worker/main.py, local) como el
handler push de Pub/Sub (worker/push_handler.py, GCP)."""

from dataclasses import dataclass, field

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.application.ports.verificacion_externa import FallaVerificacionExterna
from app.common.config import settings
from app.common.logging_utils import configurar_logging, log_evento
from app.infrastructure.config import resolver_adaptador_externo

logger = configurar_logging("worker.core")


@dataclass
class IntentoResultado:
    """Un intento individual — es lo que alimenta, uno a uno,
    `RegistrarIntento` (application/commands) para que el agregado de
    dominio registre su propia historia y dispare sus invariantes."""

    exito: bool
    duracion_ms: int
    error: str | None = None


@dataclass
class ResultadoProceso:
    exito: bool
    intentos: int
    motivo_falla: str | None = None
    detalle_intentos: list[IntentoResultado] = field(default_factory=list)


async def procesar_verificacion(
    verificacion_id: str, proveedor_id: str, tipo_verificador: str
) -> ResultadoProceso:
    intentos = 0
    ultimo_error: str | None = None
    detalle_intentos: list[IntentoResultado] = []
    puerto = resolver_adaptador_externo(tipo_verificador)

    @retry(
        reraise=True,
        stop=stop_after_attempt(settings.max_reintentos),
        wait=wait_exponential_jitter(initial=settings.backoff_base_s, max=settings.backoff_max_s),
        retry=retry_if_exception_type(
            (FallaVerificacionExterna, httpx.TransportError, httpx.TimeoutException)
        ),
    )
    async def _intentar():
        nonlocal intentos, ultimo_error
        intentos += 1
        try:
            resultado = await puerto.verificar(proveedor_id)
            detalle_intentos.append(IntentoResultado(exito=True, duracion_ms=resultado.duracion_ms))
            log_evento(
                logger,
                "verificacion_intento_exitoso",
                verificacion_id=verificacion_id,
                tipo_verificador=tipo_verificador,
                intento=intentos,
                duracion_ms=resultado.duracion_ms,
            )
        except Exception as exc:
            ultimo_error = str(exc)
            detalle_intentos.append(
                IntentoResultado(exito=False, duracion_ms=0, error=ultimo_error)
            )
            log_evento(
                logger,
                "verificacion_intento_fallido",
                verificacion_id=verificacion_id,
                tipo_verificador=tipo_verificador,
                intento=intentos,
                error=ultimo_error,
            )
            raise

    try:
        await _intentar()
        return ResultadoProceso(exito=True, intentos=intentos, detalle_intentos=detalle_intentos)
    except Exception:  # noqa: BLE001 — reintentos agotados, se captura para enrutar a DLQ
        log_evento(
            logger,
            "verificacion_reintentos_agotados",
            verificacion_id=verificacion_id,
            tipo_verificador=tipo_verificador,
            intentos=intentos,
            motivo_falla=ultimo_error,
        )
        return ResultadoProceso(
            exito=False,
            intentos=intentos,
            motivo_falla=ultimo_error,
            detalle_intentos=detalle_intentos,
        )
