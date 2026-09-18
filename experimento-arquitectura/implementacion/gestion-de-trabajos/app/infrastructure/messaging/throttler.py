"""Sidecar Throttler (DISP-02, ver `escenarios_calidad.md`, fila DISP-02) —
dosifica el envío de webhooks de `Novedad` hacia el CRM externo "Gestión de
Agentes", respetando su límite de tasa, sin bloquear el hilo/loop principal
de Gestión de Trabajos. Es el artefacto "Sidecar/Embajador de salida" del
escenario: vive dentro de este mismo proceso (no un proceso aparte, para
mantener el skeleton simple), pero está aislado en su propio módulo de
infraestructura y solo se comunica con el resto vía los puertos
`IGestionAgentesPort` e `INovedadRepository` — nunca importa `api/` ni
`application/commands/` directamente.

Dimensionamiento de la cola (`settings.throttler_cola_tamano`, default
10_000) — mismo criterio de cálculo explícito que `k6/lib/config.js`:
se dimensiona para absorber, sin que `encolar()` tenga que bloquear más
allá del backpressure intencional, un pico de hasta 4x sobre la tasa
nominal del CRM (`settings.crm_limite_rps`, default 50 rps) durante una
ventana sostenida. Con `pico = 4 * crm_limite_rps = 200 rps` y una ventana
de absorción `T` (segundos), el excedente a acumular es
`(pico - crm_limite_rps) * T = 150 * T`. Con el default de 10_000 posiciones,
`T ≈ 10_000 / 150 ≈ 67s` de pico sostenido a 4x sin perder ningún webhook
(quedan en la cola, no se descartan). Si el pico dura más que eso, la cola
se llena y `encolar()` (un `await queue.put(...)`) empieza a esperar —
backpressure hacia quien publica la novedad (`PublicarNovedad`), nunca un
descarte silencioso; el cumplimiento del umbral real (≥99.9% de trabajos
sin pérdida) depende de que el pico observado en el experimento de carga
quede dentro de esta ventana — eso lo valida `experimento-runner`, no este
módulo.

Diseño de un único worker secuencial (tal como pide el plan de esta
tarea): el backoff de un ítem que falla retrasa a los que le siguen en la
cola durante esa espera — limitación conocida y aceptable para este PoC de
un solo proceso/una sola réplica; escalar a N workers concurrentes (cada
uno con su propio recorte del token bucket) es la extensión natural si
hace falta más throughput, fuera de alcance de este skeleton (ver
README.md, "Qué falta").

Eventos de DOMINIO vs. INTEGRACIÓN (Regla 4): este módulo es quien primero
llama a la integración saliente (`IGestionAgentesPort.enviar_webhook`,
sobre HTTP hacia el CRM) y, según el resultado, invoca
`Novedad.marcar_entregada()` / `Novedad.marcar_agotada()` — son esos
métodos, no este módulo, quienes producen los eventos de DOMINIO
`NovedadEntregada`/`NovedadAgotada`. El Throttler no publica esos eventos a
ningún broker; solo persiste el agregado ya en su nuevo estado."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from tenacity import wait_exponential_jitter

from app.application.ports.gestion_agentes import IGestionAgentesPort
from app.common.config import settings
from app.common.logging_utils import configurar_logging, log_evento
from app.domain.novedades.novedad import Novedad
from app.domain.novedades.repository import INovedadRepository

logger = configurar_logging("infrastructure.messaging.throttler")


class _TokenBucket:
    """Limita la tasa de salida a `tasa_rps` tokens/segundo — implementación
    mínima en memoria, de un solo proceso, suficiente para el único worker
    de este Sidecar en el PoC (coordinar el límite entre varias réplicas
    del servicio requeriría un token bucket compartido, p.ej. en Redis —
    fuera de alcance aquí, ver README.md "Qué falta")."""

    def __init__(self, tasa_rps: float) -> None:
        if tasa_rps <= 0:
            raise ValueError("tasa_rps debe ser positiva")
        self._tasa = tasa_rps
        self._capacidad = tasa_rps
        self._tokens = tasa_rps
        self._ultimo_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def adquirir(self) -> None:
        while True:
            async with self._lock:
                ahora = time.monotonic()
                transcurrido = ahora - self._ultimo_refill
                self._ultimo_refill = ahora
                self._tokens = min(
                    self._capacidad, self._tokens + transcurrido * self._tasa
                )
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                faltante_s = (1 - self._tokens) / self._tasa
            await asyncio.sleep(faltante_s)


@dataclass
class _EstadoIntento:
    """Duck-type mínimo de `tenacity.RetryCallState` — solo necesitamos el
    atributo `attempt_number` para reutilizar `wait_exponential_jitter` como
    calculadora pura de backoff+jitter (ver nota en `_calcular_espera`)."""

    attempt_number: int


class ThrottlerCrm:
    def __init__(
        self,
        puerto_crm: IGestionAgentesPort,
        repo: INovedadRepository,
        tasa_rps: float | None = None,
        tamano_cola: int | None = None,
        max_reintentos: int | None = None,
        backoff_base_s: float | None = None,
        backoff_max_s: float | None = None,
    ) -> None:
        self._puerto_crm = puerto_crm
        self._repo = repo
        self._bucket = _TokenBucket(tasa_rps or settings.crm_limite_rps)
        self._cola: asyncio.Queue[Novedad] = asyncio.Queue(
            maxsize=tamano_cola or settings.throttler_cola_tamano
        )
        self._max_reintentos = max_reintentos or settings.throttler_max_reintentos
        self._backoff_base_s = backoff_base_s or settings.throttler_backoff_base_s
        self._backoff_max_s = backoff_max_s or settings.throttler_backoff_max_s
        # No es un @retry de tenacity de una sola llamada: la unidad de
        # reintento aquí es "reencolar y ceder el turno al token bucket",
        # no repetir la misma corrutina en un loop cerrado — por eso se usa
        # `wait_exponential_jitter` como calculadora de espera pura en vez
        # de envolver la llamada con `@retry(...)` (comparar con
        # `DISP-03/app/worker/core.py`, donde sí aplica @retry directo
        # porque ahí el reintento SÍ es repetir la misma llamada en el
        # mismo lugar).
        self._estrategia_backoff = wait_exponential_jitter(
            initial=self._backoff_base_s, max=self._backoff_max_s
        )
        self._tarea_worker: asyncio.Task[None] | None = None

    async def encolar(self, novedad: Novedad) -> None:
        """Nunca bloquea más allá del backpressure intencional de la cola
        (ver dimensionamiento en el docstring del módulo) — no ejecuta
        ninguna llamada de red, solo `await queue.put(...)`."""
        await self._cola.put(novedad)

    def iniciar(self) -> None:
        if self._tarea_worker is None:
            self._tarea_worker = asyncio.create_task(self._bucle_worker())
            log_evento(logger, "throttler_worker_iniciado")

    async def detener(self) -> None:
        if self._tarea_worker is None:
            return
        self._tarea_worker.cancel()
        try:
            await self._tarea_worker
        except asyncio.CancelledError:
            pass
        self._tarea_worker = None
        log_evento(logger, "throttler_worker_detenido")

    async def _bucle_worker(self) -> None:
        while True:
            novedad = await self._cola.get()
            try:
                await self._procesar(novedad)
            except Exception as exc:  # noqa: BLE001 — nunca debe matar al worker
                log_evento(
                    logger,
                    "throttler_error_inesperado_procesando_novedad",
                    nivel="error",
                    novedad_id=str(novedad.id),
                    error=str(exc),
                )
            finally:
                self._cola.task_done()

    async def _procesar(self, novedad: Novedad) -> None:
        await self._bucket.adquirir()
        novedad.registrar_intento()

        resultado = await self._puerto_crm.enviar_webhook(novedad)

        if resultado.exitoso:
            novedad.marcar_entregada()
            await asyncio.to_thread(self._repo.guardar, novedad)
            log_evento(
                logger,
                "novedad_entregada",
                novedad_id=str(novedad.id),
                trabajo_id=str(novedad.trabajo_id),
                intentos=novedad.intentos,
            )
            return

        if novedad.intentos >= self._max_reintentos:
            novedad.marcar_agotada(motivo=resultado.motivo_falla)
            await asyncio.to_thread(self._repo.guardar, novedad)
            log_evento(
                logger,
                "novedad_agotada",
                nivel="warning",
                novedad_id=str(novedad.id),
                trabajo_id=str(novedad.trabajo_id),
                intentos=novedad.intentos,
                motivo_falla=resultado.motivo_falla,
            )
            return

        # Persistimos también el intento fallido (sigue PENDIENTE) para que
        # `intentos` quede trazado aunque el proceso muera antes del
        # reintento — no es estrictamente necesario para el mecanismo en
        # memoria, pero evita perder la cuenta de intentos si se agrega
        # más adelante una reconstrucción de cola desde
        # `listar_pendientes()` (ver README.md "Qué falta").
        await asyncio.to_thread(self._repo.guardar, novedad)

        espera_s = resultado.reintentar_despues_s or self._calcular_espera(
            novedad.intentos
        )
        log_evento(
            logger,
            "novedad_reintento_programado",
            novedad_id=str(novedad.id),
            trabajo_id=str(novedad.trabajo_id),
            intento=novedad.intentos,
            espera_s=round(espera_s, 3),
            motivo_falla=resultado.motivo_falla,
            origen_espera="retry_after_crm"
            if resultado.reintentar_despues_s
            else "backoff_local",
        )
        await asyncio.sleep(espera_s)
        await self._cola.put(novedad)

    def _calcular_espera(self, intento: int) -> float:
        return self._estrategia_backoff(_EstadoIntento(attempt_number=intento))
