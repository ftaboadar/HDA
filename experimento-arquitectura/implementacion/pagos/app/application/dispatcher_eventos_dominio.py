"""Despachador de eventos de DOMINIO de este microservicio (Regla 5,
criterio 4) — el agregado `Pago` nunca publica ni notifica nada por su
cuenta, solo produce eventos de dominio (`registrar_evento`); la capa de
aplicación los recoge DESPUÉS de persistir el agregado (`recoger_eventos`,
ver `application/commands/pagar_trabajo.py` y `compensar.py`) y decide qué
reacciones disparar.

NO EXISTÍA COMO ARCHIVO EXPLÍCITO EN EL PLAN DE MOVIMIENTO — se agrega aquí
porque `pagar_trabajo.py`/`compensar.py` ya importaban
`app.application.dispatcher_eventos_dominio.despachar` cuando vivían dentro
de `gestion-de-trabajos`, y ese módulo no puede moverse tal cual: allá
también despachaba el evento de DOMINIO `TrabajoFinalizado` del agregado
`Trabajo` (que se queda en `gestion-de-trabajos`, no es de Pagos). Esta es
una versión reducida, propia de Pagos, que solo conoce los eventos de
`domain/pagos/eventos.py`.

Ningún módulo reacciona todavía a `PagoMarcadoExitoso`/`PagoMarcadoFallido`/
`PagoCompensado` (este servicio no tiene tópico de integración propio) — se
despachan igual para que quede trazado el evento real, no solo la
asignación de atributo dentro de `Pago`. Extensible sin tocar `pago.py` el
día que algo deba reaccionar (ej. una notificación, o una futura
publicación de integración hacia otro microservicio)."""

from __future__ import annotations

from app.common.logging_utils import configurar_logging, log_evento
from app.domain.pagos.eventos import (
    PagoCompensado,
    PagoMarcadoExitoso,
    PagoMarcadoFallido,
)
from app.domain.seedwork.domain_event import DomainEvent

logger = configurar_logging("application.dispatcher_eventos_dominio")


async def despachar(eventos: list[DomainEvent]) -> None:
    for evento in eventos:
        if isinstance(evento, (PagoMarcadoExitoso, PagoMarcadoFallido, PagoCompensado)):
            log_evento(
                logger,
                "evento_dominio_pago_despachado",
                tipo=evento.tipo,
                pago_id=str(evento.pago_id),
                trabajo_id=str(evento.trabajo_id),
            )
