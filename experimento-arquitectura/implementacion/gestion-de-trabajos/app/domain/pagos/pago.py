"""Agregado `Pago` — raíz de agregado propia del submódulo ACL de Pagos
(distinta de `Trabajo`, aunque vivan en el mismo microservicio/BD). No
existe en 07-vista-informacion.puml (ver docstring de
`domain/trabajo/trabajo.py` para la nota de inconsistencia explícita) —
Pagos es un `GENERIC_SUBDOMAIN` comprado (Stripe/MercadoPago), este
agregado es solo el registro local de qué se le pidió cobrar/compensar a
ese sistema externo, no una reimplementación de su dominio."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.domain.pagos.eventos import (
    PagoCompensado,
    PagoMarcadoExitoso,
    PagoMarcadoFallido,
)
from app.domain.pagos.value_objects import EstadoPago, PagoId, Pasarela
from app.domain.seedwork.aggregate_root import AggregateRoot
from app.domain.trabajo.value_objects import Dinero, Region, TrabajoId


class ErrorTransicionInvalidaPago(Exception):
    """Invariantes protegidos dentro del agregado, nunca desde fuera —
    mismo principio que `Trabajo.ErrorTransicionInvalida`."""


class Pago(AggregateRoot):
    def __init__(
        self,
        id: uuid.UUID,
        trabajo_id: TrabajoId,
        monto: Dinero,
        region: Region,
        pasarela: Pasarela,
        estado: EstadoPago = EstadoPago.PENDIENTE,
        referencia_externa: str | None = None,
        motivo_falla: str | None = None,
        creado_en: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self.trabajo_id = trabajo_id
        self.monto = monto
        self.region = region
        self.pasarela = pasarela
        self.estado = estado
        self.referencia_externa = referencia_externa
        self.motivo_falla = motivo_falla
        self.creado_en = creado_en or datetime.now(timezone.utc)

    def marcar_exitoso(self, referencia_externa: str) -> None:
        """Invariante: solo se puede marcar exitoso un pago PENDIENTE — no
        se puede cobrar dos veces el mismo registro de Pago (para
        reintentar, se crea un `Pago` nuevo, ver
        application/commands/pagar_trabajo.py)."""
        if self.estado != EstadoPago.PENDIENTE:
            raise ErrorTransicionInvalidaPago(
                f"No se puede marcar exitoso un pago en estado {self.estado}"
            )
        self.estado = EstadoPago.EXITOSO
        self.referencia_externa = referencia_externa
        self.motivo_falla = None
        self.registrar_evento(
            PagoMarcadoExitoso(
                pago_id=PagoId(self.id),
                trabajo_id=self.trabajo_id,
                referencia_externa=referencia_externa,
            )
        )

    def marcar_fallido(self, motivo: str) -> None:
        if self.estado != EstadoPago.PENDIENTE:
            raise ErrorTransicionInvalidaPago(
                f"No se puede marcar fallido un pago en estado {self.estado}"
            )
        self.estado = EstadoPago.FALLIDO
        self.motivo_falla = motivo
        self.registrar_evento(
            PagoMarcadoFallido(
                pago_id=PagoId(self.id), trabajo_id=self.trabajo_id, motivo=motivo
            )
        )

    def compensar(self) -> None:
        """Invariante: solo un pago EXITOSO puede compensarse (reversarse)
        — no tiene sentido reversar un pago que nunca se cobró."""
        if self.estado != EstadoPago.EXITOSO:
            raise ErrorTransicionInvalidaPago(
                f"Solo se puede compensar un pago EXITOSO, estado actual: {self.estado}"
            )
        self.estado = EstadoPago.COMPENSADO
        self.registrar_evento(
            PagoCompensado(pago_id=PagoId(self.id), trabajo_id=self.trabajo_id)
        )
