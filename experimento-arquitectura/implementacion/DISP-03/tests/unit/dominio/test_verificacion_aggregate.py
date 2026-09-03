"""Pruebas del agregado Verificacion — los 2 invariantes documentados en
app/domain/verificacion/verificacion.py son el corazón de lo que la Regla 5
(criterio 1) pide demostrar: reglas de negocio protegidas DENTRO del
agregado, no en un handler HTTP o un `if` disperso en la infraestructura."""

import pytest

from app.domain.verificacion.eventos import (
    IntentoRegistrado,
    VerificacionAgotoReintentos,
    VerificacionCompletada,
)
from app.domain.verificacion.fabrica import FabricaVerificacion
from app.domain.verificacion.value_objects import (
    EstadoVerificacion,
    ProveedorId,
    ResultadoIntento,
    TipoVerificador,
)
from app.domain.verificacion.verificacion import ErrorTransicionInvalida


def _nueva():
    return FabricaVerificacion.crear(ProveedorId("prov-1"), TipoVerificador.CERTIFICADORA)


def test_fabrica_crea_en_pendiente_sin_intentos():
    v = _nueva()
    assert v.estado == EstadoVerificacion.PENDIENTE
    assert v.intentos == []


def test_intento_exitoso_completa_y_emite_evento():
    v = _nueva()
    v.registrar_intento(ResultadoIntento.EXITOSO, duracion_ms=50)

    assert v.estado == EstadoVerificacion.COMPLETADA
    eventos = v.recoger_eventos()
    tipos = [type(e) for e in eventos]
    assert IntentoRegistrado in tipos
    assert VerificacionCompletada in tipos


def test_intentos_fallidos_agotan_y_mueven_a_dlq():
    v = _nueva()
    for _ in range(v.max_intentos):
        v.registrar_intento(ResultadoIntento.FALLIDO, duracion_ms=10, error="timeout")

    assert v.estado == EstadoVerificacion.FALLIDA_DLQ
    eventos = v.recoger_eventos()
    assert any(isinstance(e, VerificacionAgotoReintentos) for e in eventos)


def test_no_salta_directo_a_dlq_sin_agotar_intentos():
    """Invariante 2, verificado desde el camino público: con menos intentos
    fallidos que max_intentos, el estado se queda PENDIENTE — nunca
    FALLIDA_DLQ."""
    v = _nueva()
    v.registrar_intento(ResultadoIntento.FALLIDO, duracion_ms=10, error="timeout")
    assert v.estado == EstadoVerificacion.PENDIENTE


def test_no_se_puede_registrar_intento_sobre_verificacion_completada():
    v = _nueva()
    v.registrar_intento(ResultadoIntento.EXITOSO, duracion_ms=50)

    with pytest.raises(ErrorTransicionInvalida):
        v.registrar_intento(ResultadoIntento.EXITOSO, duracion_ms=50)


def test_reprocesar_solo_valido_desde_dlq():
    v = _nueva()
    with pytest.raises(ErrorTransicionInvalida):
        v.reprocesar()  # todavía PENDIENTE, no FALLIDA_DLQ


def test_reprocesar_reinicia_intentos_y_cuenta_reprocesos():
    v = _nueva()
    for _ in range(v.max_intentos):
        v.registrar_intento(ResultadoIntento.FALLIDO, duracion_ms=10, error="timeout")
    assert v.estado == EstadoVerificacion.FALLIDA_DLQ

    v.reprocesar()

    assert v.estado == EstadoVerificacion.PENDIENTE
    assert v.intentos == []
    assert v.reprocesos == 1
