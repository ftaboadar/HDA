"""Base compartida para los 3 adaptadores HTTP. Los 3 sistemas reales
(Policía Nacional, RUES, la certificadora) hablarán protocolos distintos en
producción — hoy los 3 mocks comparten forma HTTP por simplicidad del PoC,
así que el puerto (`IVerificacionExternaPort`) no debe asumir eso, pero SÍ
es razonable que los 3 adaptadores compartan la mecánica HTTP mientras esa
simplificación siga siendo cierta. Cuando alguno deje de ser HTTP, deja de
extender esta base — no rompe a los otros dos."""

import time

import httpx

from app.application.ports.verificacion_externa import (
    FallaVerificacionExterna,
    IVerificacionExternaPort,
    ResultadoVerificacionExterna,
)
from app.common.config import settings


class _AdaptadorHttpGenerico(IVerificacionExternaPort):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def verificar(self, proveedor_id: str) -> ResultadoVerificacionExterna:
        inicio = time.time()
        try:
            async with httpx.AsyncClient(timeout=settings.timeout_externo_s) as cliente:
                resp = await cliente.post(
                    f"{self._base_url}/verificar", json={"proveedor_id": proveedor_id}
                )
            duracion_ms = int((time.time() - inicio) * 1000)
            if resp.status_code >= 500:
                raise FallaVerificacionExterna(f"HTTP {resp.status_code} de {self._base_url}")
            resp.raise_for_status()
            return ResultadoVerificacionExterna(exito=True, duracion_ms=duracion_ms)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise FallaVerificacionExterna(str(exc)) from exc
