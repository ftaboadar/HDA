"""Prueba del comando `Compensar` — con fake en memoria, sin BD. Regla 5,
criterio 4: verifica que el evento de dominio `PagoCompensado` que
`Pago.compensar()` registra efectivamente se recoge y se despacha, en vez
de perderse en silencio (hallazgo de re-auditoría, ver docstring de
compensar.py)."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.application.commands.compensar import Compensar, PagoNoEncontrado
from app.domain.pagos.eventos import PagoCompensado
from app.domain.pagos.fabrica import FabricaPago
from app.domain.pagos.pago import Pago
from app.domain.pagos.value_objects import Dinero, EstadoPago, Pasarela, Region, TrabajoId


class _PagoRepositorioFalso:
    def __init__(self, pago: Pago | None = None) -> None:
        self._pago = pago

    def guardar(self, pago: Pago) -> None:
        self._pago = pago

    def obtener_por_id(self, id):
        return self._pago if self._pago and self._pago.id == id.valor else None

    def listar_por_trabajo(self, trabajo_id):
        raise NotImplementedError


def _pago_exitoso() -> Pago:
    pago = FabricaPago.crear(
        trabajo_id=TrabajoId(uuid.uuid4()),
        monto=Dinero(Decimal(50000), "COP"),
        region=Region.COLOMBIA,
        pasarela=Pasarela.STRIPE,
    )
    pago.marcar_exitoso("ch_123")
    pago.recoger_eventos()  # limpia el evento de marcar_exitoso, no es el foco de esta prueba
    return pago


@pytest.mark.asyncio
async def test_compensar_despacha_el_evento_pago_compensado():
    pago = _pago_exitoso()
    repo = _PagoRepositorioFalso(pago)
    comando = Compensar(repo)

    with patch(
        "app.application.commands.compensar.despachar", new_callable=AsyncMock
    ) as despachar_falso:
        await comando.ejecutar(str(pago.id))

    despachar_falso.assert_awaited_once()
    (eventos_despachados,), _ = despachar_falso.call_args
    assert len(eventos_despachados) == 1
    assert isinstance(eventos_despachados[0], PagoCompensado)


@pytest.mark.asyncio
async def test_compensar_pago_inexistente_lanza_error():
    repo = _PagoRepositorioFalso(pago=None)
    comando = Compensar(repo)

    with pytest.raises(PagoNoEncontrado):
        await comando.ejecutar(str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_compensar_transiciona_el_estado():
    pago = _pago_exitoso()
    repo = _PagoRepositorioFalso(pago)
    comando = Compensar(repo)

    with patch("app.application.commands.compensar.despachar", new_callable=AsyncMock):
        await comando.ejecutar(str(pago.id))

    assert pago.estado == EstadoPago.COMPENSADO
