"""Pruebas de dominio puro del agregado `PerfilReputacion` (Event Sourcing)
-- sin infraestructura, sin Event Store real, sin BD. Cubren:

1. Reconstrucción desde una lista de eventos ya persistidos.
2. Aplicar un evento nuevo (a través del método de negocio `calificar()`).
3. Al menos una invariante de dominio (rango de puntaje 1-5)."""

import pytest

from app.domain.reputacion.eventos import ProveedorCalificado
from app.domain.reputacion.perfil_reputacion import (
    PerfilReputacion,
    PuntajeFueraDeRango,
)
from app.domain.reputacion.value_objects import Garantia, ProveedorId, TrabajoId


def test_crear_perfil_nuevo_no_tiene_calificaciones_ni_eventos_pendientes():
    perfil = PerfilReputacion.crear(ProveedorId("prov-1"))

    assert perfil.calificaciones == []
    assert perfil.promedio == 0.0
    assert perfil.version == 0
    assert perfil.recoger_eventos_no_confirmados() == []


def test_calificar_aplica_el_evento_y_lo_deja_pendiente_de_persistir():
    perfil = PerfilReputacion.crear(ProveedorId("prov-1"))

    perfil.calificar(
        trabajo_id=TrabajoId("trabajo-1"), puntaje=5, comentario="Excelente"
    )

    assert len(perfil.calificaciones) == 1
    assert perfil.calificaciones[0].puntaje == 5
    assert perfil.promedio == 5.0
    assert perfil.version == 1

    pendientes = perfil.recoger_eventos_no_confirmados()
    assert len(pendientes) == 1
    assert isinstance(pendientes[0], ProveedorCalificado)
    # recoger_eventos_no_confirmados() limpia el buffer -- una segunda
    # llamada no debe repetir el mismo evento.
    assert perfil.recoger_eventos_no_confirmados() == []


def test_calificar_puntaje_fuera_de_rango_lanza_excepcion_de_dominio():
    perfil = PerfilReputacion.crear(ProveedorId("prov-1"))

    with pytest.raises(PuntajeFueraDeRango):
        perfil.calificar(trabajo_id=TrabajoId("trabajo-1"), puntaje=0)

    with pytest.raises(PuntajeFueraDeRango):
        perfil.calificar(trabajo_id=TrabajoId("trabajo-1"), puntaje=6)

    # La invariante se protege ANTES de mutar estado -- ningún evento
    # inválido queda registrado.
    assert perfil.calificaciones == []
    assert perfil.version == 0


def test_desde_eventos_reconstruye_el_mismo_estado_que_aplicar_en_vivo():
    eventos = [
        ProveedorCalificado(
            proveedor_id=ProveedorId("prov-1"),
            trabajo_id=TrabajoId("trabajo-1"),
            puntaje=4,
            comentario="Bueno",
        ),
        ProveedorCalificado(
            proveedor_id=ProveedorId("prov-1"),
            trabajo_id=TrabajoId("trabajo-2"),
            puntaje=2,
            comentario=None,
            garantia=Garantia(15),
        ),
    ]

    perfil = PerfilReputacion.desde_eventos(eventos)

    assert perfil.proveedor_id == ProveedorId("prov-1")
    assert perfil.id == "prov-1"
    assert len(perfil.calificaciones) == 2
    assert perfil.promedio == 3.0  # (4 + 2) / 2
    assert perfil.version == 2
    # Reconstruir desde eventos ya persistidos NO debe dejar nada pendiente
    # de volver a guardar -- si esto fallara, un `guardar_eventos` posterior
    # duplicaría eventos ya existentes en el Event Store.
    assert perfil.recoger_eventos_no_confirmados() == []


def test_promedio_se_recalcula_con_multiples_calificaciones():
    perfil = PerfilReputacion.crear(ProveedorId("prov-1"))

    perfil.calificar(trabajo_id=TrabajoId("t1"), puntaje=5)
    perfil.calificar(trabajo_id=TrabajoId("t2"), puntaje=3)
    perfil.calificar(trabajo_id=TrabajoId("t3"), puntaje=4)

    assert perfil.promedio == pytest.approx(4.0)
    assert perfil.version == 3
    assert len(perfil.recoger_eventos_no_confirmados()) == 3
