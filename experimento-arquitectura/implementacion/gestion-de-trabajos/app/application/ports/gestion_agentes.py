"""Puerto de aplicación hacia el CRM SaaS externo "Gestión de Agentes"
(DISP-02, ver `escenarios_calidad.md`) — el `Throttler`
(`infrastructure/messaging/throttler.py`) programa contra esta interfaz,
nunca contra `httpx` directo. El adaptador concreto
(`AdaptadorGestionAgentesHttp`) vive en
`app/infrastructure/adapters/throttler_crm.py`; el doble de prueba (mock
del CRM) lo implementa otro agente en `implementacion/mocks-crm/` contra
este mismo contrato HTTP implícito (`POST {crm_mock_url}/webhooks`).

Distinción explícita (Regla 4 de REGLAS-DURAS-rubrica-entrega-3.md): la
llamada que resuelve este puerto es la INTEGRACIÓN saliente hacia un
sistema externo, no un evento de dominio — compárese con
`NovedadEntregada`/`NovedadAgotada` en `domain/novedades/eventos.py`, que sí
son eventos de dominio y nunca llegan a este puerto directamente (es el
resultado de esta llamada, interpretado por el `Throttler`, lo que dispara
esas transiciones en el agregado)."""

from __future__ import annotations

import abc
from dataclasses import dataclass

from app.domain.novedades.novedad import Novedad


@dataclass(frozen=True)
class ResultadoEnvioWebhook:
    """DTO de aplicación — no es un Value Object de dominio: transporta el
    resultado crudo de una llamada HTTP (incluyendo `Retry-After`, un
    detalle de protocolo HTTP) hacia el `Throttler`, que es quien decide su
    política de reintento."""

    exitoso: bool
    motivo_falla: str | None = None
    reintentar_despues_s: float | None = None
    status_http: int | None = None
    duracion_ms: float | None = None


class IGestionAgentesPort(abc.ABC):
    @abc.abstractmethod
    async def enviar_webhook(self, novedad: Novedad) -> ResultadoEnvioWebhook: ...
