"""Pruebas de dominio puro sobre el agregado `Trabajo` — sin BD, sin
Pulsar, sin FastAPI."""

import uuid
from decimal import Decimal

import pytest

from app.domain.trabajo.eventos import TrabajoFinalizado
from app.domain.trabajo.fabrica import FabricaTrabajo
from app.domain.trabajo.trabajo import ErrorTransicionInvalida
from app.domain.trabajo.value_objects import EstadoTrabajo, ProveedorId, Region


def _crear_trabajo():
    return FabricaTrabajo.crear(
        proveedor_id=ProveedorId(str(uuid.uuid4())),
        monto=Decimal(100000),
        region=Region.COLOMBIA,
    )


def test_fabrica_crea_trabajo_pendiente_sin_eventos():
    trabajo = _crear_trabajo()

    assert trabajo.estado == EstadoTrabajo.PENDIENTE
    assert trabajo.monto.moneda == "COP"
    assert trabajo.recoger_eventos() == []


def test_finalizar_transiciona_a_finalizado_y_registra_evento_de_dominio():
    trabajo = _crear_trabajo()

    trabajo.finalizar()

    assert trabajo.estado == EstadoTrabajo.FINALIZADO
    eventos = trabajo.recoger_eventos()
    assert len(eventos) == 1
    assert isinstance(eventos[0], TrabajoFinalizado)
    assert eventos[0].trabajo_id.valor == trabajo.id
    assert eventos[0].region == Region.COLOMBIA


def test_recoger_eventos_limpia_el_buffer():
    trabajo = _crear_trabajo()
    trabajo.finalizar()

    primera_recoleccion = trabajo.recoger_eventos()
    segunda_recoleccion = trabajo.recoger_eventos()

    assert len(primera_recoleccion) == 1
    assert segunda_recoleccion == []


def test_no_se_puede_finalizar_un_trabajo_ya_finalizado():
    """Invariante real protegido dentro del agregado — Regla 5, criterio 1."""
    trabajo = _crear_trabajo()
    trabajo.finalizar()

    with pytest.raises(ErrorTransicionInvalida):
        trabajo.finalizar()
