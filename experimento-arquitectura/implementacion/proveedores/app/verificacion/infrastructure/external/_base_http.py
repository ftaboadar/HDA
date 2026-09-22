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
    def __init__(self, fail_max=3, reset_timeout=10):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.state = "CLOSED"
        self.last_failure_time = None

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
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
        return wrapper

_circuit_breaker = CircuitBreaker()


class _AdaptadorHttpGenerico(IVerificacionExternaPort):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    @_circuit_breaker
    async def verificar(self, proveedor_id: str) -> ResultadoVerificacionExterna:
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
