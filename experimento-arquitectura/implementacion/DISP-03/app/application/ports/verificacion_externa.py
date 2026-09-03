"""Segundo puerto que cierra el hueco de hexagonal que hoy existe en
worker/core.py: la llamada a `httpx` hacia Policía/RUES/Certificadora es
directa, sin puerto de por medio. Con esto, el dominio/aplicación depende de
una abstracción, no de un cliente HTTP concreto — los 3 adaptadores viven en
app/infrastructure/external/."""

import abc
from dataclasses import dataclass


class FallaVerificacionExterna(Exception):
    pass


@dataclass(frozen=True)
class ResultadoVerificacionExterna:
    exito: bool
    duracion_ms: int
    error: str | None = None


class IVerificacionExternaPort(abc.ABC):
    @abc.abstractmethod
    async def verificar(self, proveedor_id: str) -> ResultadoVerificacionExterna: ...
