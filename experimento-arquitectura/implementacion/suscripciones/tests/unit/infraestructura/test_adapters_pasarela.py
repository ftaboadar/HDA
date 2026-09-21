"""Contrato de los Adapters de pasarela (MOD-02): cada uno traduce el mismo
`Pago` del dominio (siempre en unidades) al formato que su pasarela real
espera. Sin HTTP real — se intercepta `httpx.AsyncClient.post`."""

import uuid
from decimal import Decimal

import httpx
import pytest

from app.domain.pagos.fabrica import FabricaPago
from app.domain.pagos.value_objects import Dinero, Pasarela, Region, TrabajoId
from app.infrastructure.adapters.pasarela_mercadopago import PasarelaMercadoPago
from app.infrastructure.adapters.pasarela_stripe import PasarelaStripe


def _pago(valor: str, moneda: str, region: Region, pasarela: Pasarela):
    return FabricaPago.crear(
        trabajo_id=TrabajoId(uuid.uuid4()),
        monto=Dinero(Decimal(valor), moneda),
        region=region,
        pasarela=pasarela,
    )


@pytest.fixture
def capturar_post(monkeypatch):
    enviados: list[tuple[str, dict]] = []

    async def post_falso(self, url, json=None, **_):
        enviados.append((url, json))
        return httpx.Response(
            200, json={"id": "ref-123"}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", post_falso)
    return enviados


@pytest.mark.asyncio
async def test_stripe_envia_centavos_como_entero(capturar_post):
    pago = _pago("200.50", "COP", Region.COLOMBIA, Pasarela.STRIPE)

    resultado = await PasarelaStripe(base_url="http://stripe").cobrar(pago)

    url, payload = capturar_post[0]
    assert url == "http://stripe/v1/charges"
    assert payload["amount"] == 20050
    assert isinstance(payload["amount"], int)
    assert resultado.exitoso


@pytest.mark.asyncio
async def test_mercadopago_envia_unidades(capturar_post):
    pago = _pago("200.50", "BRL", Region.BRASIL, Pasarela.MERCADOPAGO)

    resultado = await PasarelaMercadoPago(base_url="http://mp").cobrar(pago)

    url, payload = capturar_post[0]
    assert url == "http://mp/v1/payments"
    assert payload["transaction_amount"] == 200.5
    assert resultado.exitoso
