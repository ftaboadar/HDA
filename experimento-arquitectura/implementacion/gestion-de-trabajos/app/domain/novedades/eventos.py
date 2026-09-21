"""Eventos de DOMINIO del agregado `Novedad` — internos a este servicio
(Gestión de Trabajos), producidos únicamente por el propio agregado al
transicionar de estado (ver `domain/seedwork/domain_event.py` para la
distinción general dominio/integración, ya documentada para `Trabajo`).

Distinción explícita para este flujo (DISP-02, Sidecar/Throttler, ver
`escenarios_calidad.md`):
- Evento de DOMINIO: `NovedadEntregada` / `NovedadAgotada` — nacen dentro de
  `Novedad.marcar_entregada()` / `Novedad.marcar_agotada()`, no conocen HTTP
  ni el CRM, no cruzan el proceso por sí solos.
- Evento/mensaje de INTEGRACIÓN saliente: el POST HTTP que
  `infrastructure/adapters/throttler_crm.py` (`AdaptadorGestionAgentesHttp`)
  envía a `settings.crm_mock_url + "/webhooks"` — eso es la comunicación con
  un sistema EXTERNO (CRM SaaS "Gestión de Agentes"), completamente distinta
  del evento de dominio; es lo que dispara la transición de estado, pero no
  es el mismo objeto ni cruza por el mismo canal.
- No hay, en este skeleton, una reacción intra-servicio adicional
  suscrita a estos dos eventos de dominio (a diferencia de
  `application/dispatcher_eventos_dominio.py` para `TrabajoFinalizado`,
  que sí puebla un registro local) — el agregado los registra igual porque
  es el punto correcto del diseño para engancharla si aparece un
  consumidor real (p.ej. un módulo de auditoría de entregas); se deja
  explícito en vez de omitir el evento por no tener todavía un
  suscriptor."""

from dataclasses import dataclass

from app.domain.novedades.value_objects import NovedadId
from app.domain.seedwork.domain_event import DomainEvent
from app.domain.ciclo_vida.value_objects import TrabajoId


@dataclass(frozen=True)
class NovedadEntregada(DomainEvent):
    novedad_id: NovedadId
    trabajo_id: TrabajoId
    intentos: int


@dataclass(frozen=True)
class NovedadAgotada(DomainEvent):
    novedad_id: NovedadId
    trabajo_id: TrabajoId
    intentos: int
    motivo: str | None = None
