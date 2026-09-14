"""Pruebas de dominio puro -- sin infraestructura, sin BD, sin FastAPI."""

import pytest

from app.domain.reputacion.value_objects import Garantia, ProveedorId, TrabajoId


def test_proveedor_id_vacio_lanza_error():
    with pytest.raises(ValueError):
        ProveedorId("")


def test_trabajo_id_vacio_lanza_error():
    with pytest.raises(ValueError):
        TrabajoId("")


def test_garantia_negativa_lanza_error():
    with pytest.raises(ValueError):
        Garantia(-1)


def test_value_objects_son_iguales_por_valor_no_por_identidad():
    assert ProveedorId("prov-1") == ProveedorId("prov-1")
    assert ProveedorId("prov-1") != ProveedorId("prov-2")
    assert Garantia(30) == Garantia(30)
