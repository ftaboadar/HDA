"""Pruebas unitarias de dominio puro — sin BD, sin HTTP, sin FastAPI. Corren
en milisegundos y no necesitan docker-compose levantado."""

import uuid

import pytest

from app.domain.verificacion.value_objects import ProveedorId, VerificacionId


def test_verificacion_id_nueva_es_unica():
    a = VerificacionId.nueva()
    b = VerificacionId.nueva()
    assert a != b


def test_verificacion_id_igualdad_por_valor():
    valor = uuid.uuid4()
    assert VerificacionId(valor) == VerificacionId(valor)


def test_proveedor_id_rechaza_vacio():
    with pytest.raises(ValueError):
        ProveedorId("")


def test_proveedor_id_str():
    assert str(ProveedorId("prov-123")) == "prov-123"
