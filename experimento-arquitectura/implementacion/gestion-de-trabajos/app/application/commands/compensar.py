"""Comando `Compensar` — reversa un pago ya exitoso (invariante protegido
en `Pago.compensar()`). CQS: retorna solo el `id` del pago compensado.

Alcance de skeleton, dejado explícito: este comando marca el estado de
dominio como COMPENSADO pero NO llama todavía a un endpoint de reversa en
la pasarela externa — `IPasarelaDePago` solo define `cobrar()` (ver
app/application/ports/pasarela_de_pago.py). Ver README.md, sección "Qué
falta": agregar `reversar(pago) -> ResultadoReversa` al puerto es el
siguiente paso natural, no incluido aquí para no inventar un contrato sin
que el mock de Johan (implementacion/mocks-pagos/) lo soporte todavía.

Regla 5, criterio 4: `pago.compensar()` registra el evento de dominio
`PagoCompensado` (ver app/domain/pagos/pago.py) — este comando, igual que
`pagar_trabajo.py`, lo recoge y lo pasa al dispatcher DESPUÉS de persistir
el agregado, nunca antes (hallazgo de re-auditoría corregido: antes este
comando dejaba el evento acumulado en el agregado sin recogerlo ni
despacharlo, perdiéndose en silencio al salir de scope).

CORRECCIÓN (encontrada corriendo k6 real contra GCP, ver
`crear_trabajo.py` para el hallazgo completo): `_pago_repo` es síncrono —
envuelto en `asyncio.to_thread` para no bloquear el event loop."""

import asyncio
import uuid

from app.application.dispatcher_eventos_dominio import despachar
from app.common.logging_utils import configurar_logging, log_evento
from app.domain.pagos.repository import IPagoRepository
from app.domain.pagos.value_objects import PagoId

logger = configurar_logging("application.commands.compensar")


class PagoNoEncontrado(Exception):
    pass


class Compensar:
    def __init__(self, pago_repo: IPagoRepository) -> None:
        self._pago_repo = pago_repo

    async def ejecutar(self, pago_id: str) -> uuid.UUID:
        pago = await asyncio.to_thread(
            self._pago_repo.obtener_por_id, PagoId.desde_str(pago_id)
        )
        if pago is None:
            raise PagoNoEncontrado(pago_id)

        pago.compensar()
        await asyncio.to_thread(self._pago_repo.guardar, pago)
        await despachar(pago.recoger_eventos())

        log_evento(logger, "pago_compensado", pago_id=pago_id)
        return pago.id
