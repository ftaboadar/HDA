"""Pruebas de dominio puro sobre el agregado `Pago` (submódulo ACL de
Pagos) — sin BD, sin HTTP hacia Stripe/MercadoPago."""

import uuid
from decimal import Decimal

import pytest

from app.domain.pagos.eventos import (
    PagoCompensado,
    PagoMarcadoExitoso,
    PagoMarcadoFallido,
)
from app.domain.pagos.fabrica import FabricaPago
from app.domain.pagos.pago import ErrorTransicionInvalidaPago
from app.domain.pagos.value_objects import EstadoPago, Pasarela
from app.domain.trabajo.value_objects import Dinero, Region, TrabajoId


def _crear_pago():
    return FabricaPago.crear(
        trabajo_id=TrabajoId(uuid.uuid4()),
        monto=Dinero(Decimal(50000), "COP"),
        region=Region.COLOMBIA,
        pasarela=Pasarela.STRIPE,
    )


def test_fabrica_crea_pago_pendiente():
    pago = _crear_pago()
    assert pago.estado == EstadoPago.PENDIENTE
    assert pago.referencia_externa is None


def test_marcar_exitoso_transiciona_y_guarda_referencia():
    pago = _crear_pago()

    pago.marcar_exitoso("ch_123")

    assert pago.estado == EstadoPago.EXITOSO
    assert pago.referencia_externa == "ch_123"


def test_marcar_exitoso_registra_evento_de_dominio():
    """Antes, ninguna transición de Pago registraba un evento de dominio —
    era solo asignación de atributo. Regla 5, criterio 4."""
    pago = _crear_pago()

    pago.marcar_exitoso("ch_123")

    eventos = pago.recoger_eventos()
    assert len(eventos) == 1
    assert isinstance(eventos[0], PagoMarcadoExitoso)
    assert eventos[0].pago_id.valor == pago.id
    assert eventos[0].referencia_externa == "ch_123"


def test_marcar_fallido_transiciona_y_guarda_motivo():
    pago = _crear_pago()

    pago.marcar_fallido("tarjeta rechazada")

    assert pago.estado == EstadoPago.FALLIDO
    assert pago.motivo_falla == "tarjeta rechazada"


def test_marcar_fallido_registra_evento_de_dominio():
    pago = _crear_pago()

    pago.marcar_fallido("tarjeta rechazada")

    eventos = pago.recoger_eventos()
    assert len(eventos) == 1
    assert isinstance(eventos[0], PagoMarcadoFallido)
    assert eventos[0].motivo == "tarjeta rechazada"


def test_no_se_puede_marcar_exitoso_dos_veces():
    """Invariante: un mismo registro de Pago no se cobra dos veces."""
    pago = _crear_pago()
    pago.marcar_exitoso("ch_123")

    with pytest.raises(ErrorTransicionInvalidaPago):
        pago.marcar_exitoso("ch_456")


def test_compensar_requiere_pago_exitoso():
    """Invariante: no se puede reversar un pago que nunca se cobró."""
    pago = _crear_pago()

    with pytest.raises(ErrorTransicionInvalidaPago):
        pago.compensar()

    pago.marcar_exitoso("ch_123")
    pago.recoger_eventos()  # limpia el evento de marcar_exitoso, no es el foco de esta prueba
    pago.compensar()
    assert pago.estado == EstadoPago.COMPENSADO

    eventos = pago.recoger_eventos()
    assert len(eventos) == 1
    assert isinstance(eventos[0], PagoCompensado)
