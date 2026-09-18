"""Pruebas de dominio puro sobre el agregado `Novedad` (DISP-02) — sin BD,
sin HTTP, sin el Throttler. Mismo estilo que `test_trabajo_aggregate.py`."""

import uuid

import pytest

from app.domain.novedades.eventos import NovedadAgotada, NovedadEntregada
from app.domain.novedades.fabrica import FabricaNovedad
from app.domain.novedades.novedad import ErrorTransicionInvalida
from app.domain.novedades.value_objects import EstadoNovedad
from app.domain.trabajo.value_objects import TrabajoId


def _crear_novedad():
    return FabricaNovedad.crear(
        trabajo_id=TrabajoId(uuid.uuid4()),
        descripcion="El cliente reportó una fuga adicional",
    )


def test_fabrica_crea_novedad_pendiente_sin_eventos_ni_intentos():
    novedad = _crear_novedad()

    assert novedad.estado == EstadoNovedad.PENDIENTE
    assert novedad.intentos == 0
    assert novedad.recoger_eventos() == []


def test_fabrica_rechaza_descripcion_vacia():
    with pytest.raises(ValueError):
        FabricaNovedad.crear(trabajo_id=TrabajoId(uuid.uuid4()), descripcion="")


def test_registrar_intento_incrementa_el_contador():
    novedad = _crear_novedad()

    novedad.registrar_intento()
    novedad.registrar_intento()

    assert novedad.intentos == 2
    assert novedad.estado == EstadoNovedad.PENDIENTE


def test_marcar_entregada_transiciona_y_registra_evento_de_dominio():
    novedad = _crear_novedad()
    novedad.registrar_intento()

    novedad.marcar_entregada()

    assert novedad.estado == EstadoNovedad.ENTREGADA
    eventos = novedad.recoger_eventos()
    assert len(eventos) == 1
    assert isinstance(eventos[0], NovedadEntregada)
    assert eventos[0].novedad_id.valor == novedad.id
    assert eventos[0].trabajo_id == novedad.trabajo_id
    assert eventos[0].intentos == 1


def test_marcar_agotada_transiciona_y_registra_evento_de_dominio_con_motivo():
    novedad = _crear_novedad()
    for _ in range(5):
        novedad.registrar_intento()

    novedad.marcar_agotada(motivo="rate_limited_429")

    assert novedad.estado == EstadoNovedad.AGOTADA
    eventos = novedad.recoger_eventos()
    assert len(eventos) == 1
    assert isinstance(eventos[0], NovedadAgotada)
    assert eventos[0].intentos == 5
    assert eventos[0].motivo == "rate_limited_429"


def test_recoger_eventos_limpia_el_buffer():
    novedad = _crear_novedad()
    novedad.marcar_entregada()

    primera_recoleccion = novedad.recoger_eventos()
    segunda_recoleccion = novedad.recoger_eventos()

    assert len(primera_recoleccion) == 1
    assert segunda_recoleccion == []


def test_no_se_puede_entregar_una_novedad_ya_entregada():
    """Invariante real protegido dentro del agregado — Regla 5, criterio 1."""
    novedad = _crear_novedad()
    novedad.marcar_entregada()

    with pytest.raises(ErrorTransicionInvalida):
        novedad.marcar_entregada()


def test_no_se_puede_entregar_una_novedad_ya_agotada():
    novedad = _crear_novedad()
    novedad.marcar_agotada()

    with pytest.raises(ErrorTransicionInvalida):
        novedad.marcar_entregada()


def test_no_se_puede_agotar_una_novedad_ya_agotada():
    novedad = _crear_novedad()
    novedad.marcar_agotada()

    with pytest.raises(ErrorTransicionInvalida):
        novedad.marcar_agotada()


def test_no_se_puede_agotar_una_novedad_ya_entregada():
    novedad = _crear_novedad()
    novedad.marcar_entregada()

    with pytest.raises(ErrorTransicionInvalida):
        novedad.marcar_agotada()


def test_no_se_pueden_registrar_intentos_sobre_una_novedad_entregada():
    novedad = _crear_novedad()
    novedad.marcar_entregada()

    with pytest.raises(ErrorTransicionInvalida):
        novedad.registrar_intento()


def test_no_se_pueden_registrar_intentos_sobre_una_novedad_agotada():
    novedad = _crear_novedad()
    novedad.marcar_agotada()

    with pytest.raises(ErrorTransicionInvalida):
        novedad.registrar_intento()
