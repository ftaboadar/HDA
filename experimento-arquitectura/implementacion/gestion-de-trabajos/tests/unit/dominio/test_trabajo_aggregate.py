"""Pruebas de dominio puro sobre el agregado `Trabajo` — sin BD, sin
Pulsar, sin FastAPI."""

import uuid
from decimal import Decimal

import pytest

from app.ciclo_vida.domain.eventos import TrabajoFinalizado
from app.ciclo_vida.domain.fabrica import FabricaTrabajo
from app.ciclo_vida.domain.trabajo import ErrorTransicionInvalida
from app.ciclo_vida.domain.value_objects import EstadoTrabajo, ProveedorId, Region


def _crear_trabajo():
    return FabricaTrabajo.crear(
        monto=Decimal(100000),
        region=Region.COLOMBIA,
        proveedor_id=ProveedorId(str(uuid.uuid4())),
    )


def _crear_trabajo_en_curso():
    """Camina la máquina de estados real (15-arquitectura-entrega-5.md §6)
    hasta EN_CURSO -- precondición de `finalizar()` -- en vez de llamar
    `finalizar()` directo sobre un trabajo recién creado en SOLICITADO
    (eso lanzaba `ErrorTransicionInvalida`, ver coordinador.py bug #6)."""
    trabajo = _crear_trabajo()
    trabajo.asignar_proveedor(trabajo.proveedor_id)
    trabajo.iniciar_workflow()
    return trabajo


def test_fabrica_crea_trabajo_solicitado_sin_eventos():
    trabajo = _crear_trabajo()

    assert trabajo.estado == EstadoTrabajo.SOLICITADO
    assert trabajo.monto.moneda == "COP"
    assert trabajo.recoger_eventos() == []


def test_finalizar_transiciona_a_finalizado_y_registra_evento_de_dominio():
    trabajo = _crear_trabajo_en_curso()

    trabajo.finalizar()

    assert trabajo.estado == EstadoTrabajo.FINALIZADO
    eventos = trabajo.recoger_eventos()
    assert len(eventos) == 1
    assert isinstance(eventos[0], TrabajoFinalizado)
    assert eventos[0].trabajo_id.valor == trabajo.id
    assert eventos[0].region == Region.COLOMBIA


def test_recoger_eventos_limpia_el_buffer():
    trabajo = _crear_trabajo_en_curso()
    trabajo.finalizar()

    primera_recoleccion = trabajo.recoger_eventos()
    segunda_recoleccion = trabajo.recoger_eventos()

    assert len(primera_recoleccion) == 1
    assert segunda_recoleccion == []


def test_no_se_puede_finalizar_un_trabajo_ya_finalizado():
    """Invariante real protegido dentro del agregado — Regla 5, criterio 1.
    Sigue probando que un SEGUNDO `finalizar()` falla (no se debilita la
    cobertura de la invariante al ajustar el helper al camino real de
    estados)."""
    trabajo = _crear_trabajo_en_curso()
    trabajo.finalizar()

    with pytest.raises(ErrorTransicionInvalida):
        trabajo.finalizar()
