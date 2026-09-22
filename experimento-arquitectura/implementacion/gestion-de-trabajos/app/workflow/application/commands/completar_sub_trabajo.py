"""Comando `CompletarSubTrabajo` (Regla 5, criterio 5 -- CQS: comando, muta
estado y no retorna el agregado). Expone el paso 5 de la saga
(15-arquitectura-entrega-5.md §5.1 y §7.1: "Proveedor -API-> GT:
CompletarSubTrabajo -> Motor -async SubTrabajosCompletos-> Ciclo de Vida:
CerrarTrabajo (FINALIZADO)") a `POST /trabajos/{trabajo_id}/completar` en
`app/api/main.py` -- la ruta HTTP nunca llama al coordinador ni al agregado
directo, solo a este comando (arquitectura hexagonal, criterio 2).

No se modela `SubTrabajo` como entidad propia en este PoC (un solo
sub-trabajo por trabajo, ver docstring de `ciclo_vida/domain/trabajo.py`):
"completar el sub-trabajo" colapsa a completar el `Trabajo` mismo.

Reutiliza `SagaHandlers.handle_completar_sub_trabajo` -- el mismo patrón de
idempotencia por `id_mensaje` + Saga Log que ya usan `handle_franja_reservada`
y `handle_pago_retenido` -- en vez de duplicar esa lógica aquí. La única
responsabilidad propia de este comando es generar un `id_mensaje` cuando el
llamador no trae uno (p. ej. una `Idempotency-Key` del cliente HTTP)."""

from __future__ import annotations

import uuid

from app.workflow.application.handlers_saga import SagaHandlers


class CompletarSubTrabajo:
    def __init__(self, handlers: SagaHandlers) -> None:
        self._handlers = handlers

    async def ejecutar(
        self, trabajo_id: uuid.UUID, id_mensaje: str | None = None
    ) -> None:
        await self._handlers.handle_completar_sub_trabajo(
            trabajo_id, id_mensaje or str(uuid.uuid4())
        )
