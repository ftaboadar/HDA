"""Despachador de eventos de dominio (Regla 5, criterio 4) — mismo
principio que `DISP-03/app/application/dispatcher_eventos_dominio.py`: el
agregado nunca publica ni notifica nada por su cuenta, solo produce eventos
de dominio (`registrar_evento`); la capa de aplicación los recoge DESPUÉS
de persistir el agregado (`recoger_eventos`) y decide qué reacciones
disparar. Antes de este archivo, `CrearTrabajo.ejecutar()` recogía y
publicaba el evento de integración en la misma función que lo generaba —
sin ningún punto de despacho desacoplado ni ninguna reacción de otro módulo
del servicio (hallazgo de auditoría, Regla 5 criterio 4).

Reacciones registradas para `TrabajoFinalizado`:
1. Registro local `IRegistroTrabajosRepository`
   (`application/ports/registro_trabajos.py`): deja trazado qué trabajos
   finalizaron y en qué términos, sin acoplar este módulo a nada externo.
2. Evento de INTEGRACIÓN hacia otros microservicios (Proveedores,
   Reputación) vía `IPublicador` — mismo comportamiento que existía antes,
   solo que ahora vive aquí en vez de estar inline en el comando.

Separación de Pagos (ver `implementacion/pagos/README.md`): el agregado
`Pago` y sus eventos de dominio (`PagoMarcadoExitoso`, `PagoMarcadoFallido`,
`PagoCompensado`) se movieron a ese microservicio independiente — este
dispatcher ya NO los conoce ni los despacha; su propia copia de este mismo
archivo, en `implementacion/pagos/app/application/dispatcher_eventos_dominio.py`,
es quien ahora los despacha dentro de ese proceso."""

from __future__ import annotations

import asyncio

from app.application.ports.publicador import IPublicador
from app.application.ports.registro_trabajos import (
    IRegistroTrabajosRepository,
    RegistroTrabajoElegible,
)
from app.common.logging_utils import configurar_logging, log_evento
from app.domain.seedwork.domain_event import DomainEvent
from app.domain.trabajo.eventos import TrabajoFinalizado

logger = configurar_logging("application.dispatcher_eventos_dominio")


async def despachar(
    eventos: list[DomainEvent],
    *,
    publicador: IPublicador | None = None,
    registro_repo: IRegistroTrabajosRepository | None = None,
) -> None:
    for evento in eventos:
        if isinstance(evento, TrabajoFinalizado):
            await _reaccionar_trabajo_finalizado(evento, publicador, registro_repo)


async def _reaccionar_trabajo_finalizado(
    evento: TrabajoFinalizado,
    publicador: IPublicador | None,
    registro_repo: IRegistroTrabajosRepository | None,
) -> None:
    if registro_repo is not None:
        # asyncio.to_thread: registro_repo.guardar es SQLAlchemy síncrono —
        # ver docstring de application/commands/crear_trabajo.py para el
        # hallazgo completo (k6 real contra GCP, event loop bloqueado).
        await asyncio.to_thread(
            registro_repo.guardar,
            RegistroTrabajoElegible(
                trabajo_id=evento.trabajo_id,
                proveedor_id=evento.proveedor_id,
                monto=evento.monto,
                moneda=evento.moneda,
                region=evento.region,
            ),
        )

    if publicador is None:
        return

    try:
        await publicador.publicar_trabajo_finalizado(evento)
    except Exception as exc:  # noqa: BLE001
        # El trabajo ya quedó persistido correctamente antes de este punto
        # — una falla al publicar el evento de integración es una falla de
        # notificación, no de escritura, y no debe propagarse (mismo
        # principio que dispatcher_eventos_dominio.py en DISP-03). Sin DLQ
        # propia todavía en este skeleton — ver README.md, "Qué falta".
        log_evento(
            logger,
            "evento_integracion_trabajo_finalizado_fallo_publicacion",
            nivel="error",
            trabajo_id=str(evento.trabajo_id),
            error=str(exc),
        )
