"""Base compartida para los 3 adaptadores HTTP. Los 3 sistemas reales
(Policía Nacional, RUES, la certificadora) hablarán protocolos distintos en
producción — hoy los 3 mocks comparten forma HTTP por simplicidad del PoC,
así que el puerto (`IVerificacionExternaPort`) no debe asumir eso, pero SÍ
es razonable que los 3 adaptadores compartan la mecánica HTTP mientras esa
simplificación siga siendo cierta. Cuando alguno deje de ser HTTP, deja de
extender esta base — no rompe a los otros dos."""

import time

import httpx

from app.verificacion.application.ports.verificacion_externa import (
    FallaVerificacionExterna,
    IVerificacionExternaPort,
    ResultadoVerificacionExterna,
)
from app.common.config import settings
from app.common.logging_utils import (
    configurar_logging,
    headers_trace_salientes,
    log_evento,
)

logger = configurar_logging("infrastructure.external.http")


class CircuitBreaker:
    # reset_timeout=5 (antes 10): con 10s, CP-6 (DLQ -> mock se repara -> se
    # reprocesa) se volvía intermitente contra Pulsar real (visto en
    # CI/local: 1 de 5 corridas de la suite completa) — cuando la última
    # falla que abrió el breaker ocurría justo antes de que el test
    # reparara el mock, el presupuesto de reintentos de tenacity
    # (max_reintentos=4, backoff_base_s=0.5, backoff_max_s=8.0, ver
    # procesar_verificacion.py) a veces se agotaba ANTES de que pasara la
    # ventana de reset_timeout, así que la verificación quedaba
    # definitivamente en FALLIDA_DLQ aunque el externo ya estuviera sano.
    # plan.md no fija un valor de reset_timeout (el circuit breaker es
    # "extensión opcional", sección 8) — 5s deja margen cómodo dentro del
    # presupuesto de reintentos típico sin debilitar el propósito de la
    # táctica (seguir cortando llamadas mientras el externo está
    # activamente fallando).
    def __init__(self, fail_max=3, reset_timeout=5):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.state = "CLOSED"
        self.last_failure_time = None

    async def ejecutar(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise FallaVerificacionExterna("Circuit Breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            self.failures = 0
            self.state = "CLOSED"
            return result
        except Exception as e:
            self.failures += 1
            if self.failures >= self.fail_max:
                self.state = "OPEN"
                self.last_failure_time = time.time()
            raise e


# BUG REAL encontrado el 2026-09-22 corriendo CP-4/CP-5 de DISP-03 contra
# Pulsar real por primera vez (ver docker-compose.yml de este servicio):
# antes había un único `_circuit_breaker = CircuitBreaker()` a nivel de
# módulo, decorando `verificar()` en la clase BASE — es decir, UN SOLO
# breaker compartido por los 3 adaptadores (Policía, RUES, Certificadora).
# Una racha de fallos de la certificadora (CP-3/CP-4) abría el breaker
# para los tres por igual, incluida Policía, que nunca había fallado —
# rompiendo el aislamiento por integración externa que exige
# `06-vista-cyc.puml` ("ACL con circuit breaker por integración externa")
# y el propio plan.md de DISP-03 (CP-5: "0% impacto" en policía/RUES
# cuando solo la certificadora está caída). Cada adaptador CONCRETO se
# reinstancia en cada verificación (ver
# infrastructure/config.py:resolver_adaptador_externo), así que el estado
# del breaker no puede vivir en `self` — tiene que sobrevivir entre
# instancias. La solución NO es volver a un singleton único: es un
# registro a nivel de módulo keyed por `base_url`, un breaker
# independiente por sistema externo.
_circuit_breakers: dict[str, CircuitBreaker] = {}


def _breaker_de(base_url: str) -> CircuitBreaker:
    breaker = _circuit_breakers.get(base_url)
    if breaker is None:
        breaker = CircuitBreaker()
        _circuit_breakers[base_url] = breaker
    return breaker


class _AdaptadorHttpGenerico(IVerificacionExternaPort):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def verificar(self, proveedor_id: str) -> ResultadoVerificacionExterna:
        return await _breaker_de(self._base_url).ejecutar(self._verificar_sin_breaker, proveedor_id)

    async def _verificar_sin_breaker(self, proveedor_id: str) -> ResultadoVerificacionExterna:
        inicio = time.time()
        try:
            async with httpx.AsyncClient(timeout=settings.timeout_externo_s) as cliente:
                resp = await cliente.post(
                    f"{self._base_url}/verificar",
                    json={"proveedor_id": proveedor_id},
                    headers=headers_trace_salientes(),
                )
            duracion_ms = int((time.time() - inicio) * 1000)
            log_evento(
                logger,
                "verificador_externo_respuesta",
                nivel="warning" if resp.status_code >= 500 else "info",
                adaptador=type(self).__name__,
                destino=self._base_url,
                proveedor_id=proveedor_id,
                status_http=resp.status_code,
                duracion_ms=duracion_ms,
            )
            if resp.status_code >= 500:
                raise FallaVerificacionExterna(f"HTTP {resp.status_code} de {self._base_url}")
            resp.raise_for_status()
            return ResultadoVerificacionExterna(exito=True, duracion_ms=duracion_ms)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise FallaVerificacionExterna(str(exc)) from exc
