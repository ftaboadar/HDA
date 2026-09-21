"""Pruebas de dominio puro sobre la Strategy `ReglaRegional` — demuestran
MOD-02: `ReglaColombia` y `ReglaBrasil` son intercambiables detrás de la
misma interfaz, y cada una valida/calcula de forma independiente."""

import uuid
from decimal import Decimal

import pytest

from app.domain.pagos.fabrica import FabricaPago
from app.domain.pagos.value_objects import Dinero, Pasarela, Region, TrabajoId
from app.infrastructure.adapters.regla_brasil import ReglaBrasil
from app.infrastructure.adapters.regla_colombia import ReglaColombia


def _pago_con(monto: Decimal, moneda: str, region: Region) -> "Pago":  # noqa: F821
    return FabricaPago.crear(
        trabajo_id=TrabajoId(uuid.uuid4()),
        monto=Dinero(monto, moneda),
        region=region,
        pasarela=Pasarela.STRIPE,
    )


def test_regla_colombia_calcula_comision_2_9_por_ciento():
    regla = ReglaColombia()

    comision = regla.calcular_comision(Decimal(100000))

    assert comision == Decimal("2900.00")


def test_regla_colombia_rechaza_moneda_distinta_de_cop():
    regla = ReglaColombia()
    pago = _pago_con(Decimal(100), "BRL", Region.COLOMBIA)

    with pytest.raises(ValueError):
        regla.validar(pago)


def test_regla_brasil_calcula_comision_3_9_por_ciento():
    regla = ReglaBrasil()

    comision = regla.calcular_comision(Decimal(1000))

    assert comision == Decimal("39.00")


def test_regla_brasil_y_colombia_dan_comisiones_distintas_para_el_mismo_monto():
    """No es solo que existan dos clases — deben producir resultados
    distintos, o el Strategy no estaría aportando nada real."""
    monto = Decimal(10000)

    comision_co = ReglaColombia().calcular_comision(monto)
    comision_br = ReglaBrasil().calcular_comision(monto)

    assert comision_co != comision_br
