"""Prueba de MOD-02 (escenarios_calidad.md, tabla Modificabilidad) contra
código real: agregar la región Brasil (`ReglaBrasil` + `PasarelaMercadoPago`)
no debió requerir tocar `ReglaColombia`, `PasarelaStripe` ni el comando
`PagarTrabajo` en sí (patrón Strategy/Adapter puro, despacho por
`dict`/puerto inyectado — nunca por `if`/`match` comparando contra un
literal de país).

Esta prueba hace dos cosas, con fakes en memoria (mismo estilo que
`test_compensar.py`: clases fake propias para los repositorios, no
`unittest.mock` para ellos):

1. Ejecuta `PagarTrabajo.ejecutar(...)` DOS veces con la MISMA instancia del
   comando y los MISMOS diccionarios `reglas_regionales`/`pasarelas`
   inyectados — una vez con un `RegistroTrabajoElegible` de región Colombia
   (debe resolver `ReglaColombia` + `PasarelaStripe`) y otra vez con uno de
   región Brasil (debe resolver `ReglaBrasil` + `PasarelaMercadoPago`). Se
   usan las clases reales de `ReglaColombia`/`ReglaBrasil` (lógica pura, sin
   I/O) envueltas en un espía delgado para observar cuál fue invocada, y las
   clases reales de `PasarelaStripe`/`PasarelaMercadoPago` con `httpx`
   mockeado (sin red real), también envueltas en un espía.
2. Inspecciona el código fuente de `pagar_trabajo.py` con `ast` y confirma
   que no contiene ningún `if`/`match` que compare contra un literal de país
   (`"BR"`, `"CO"`, `Region.BRASIL`, `Region.COLOMBIA`) — el despacho debe
   ser puramente por diccionario/puerto inyectado.
"""

from __future__ import annotations

import ast
import inspect
import uuid
from decimal import Decimal

import pytest

import app.application.commands.pagar_trabajo as pagar_trabajo_module
from app.application.commands.pagar_trabajo import PagarTrabajo, TrabajoNoEncontrado
from app.application.ports.registro_trabajos import (
    IRegistroTrabajosRepository,
    RegistroTrabajoElegible,
)
from app.domain.pagos.pago import Pago
from app.domain.pagos.repository import IPagoRepository
from app.domain.pagos.value_objects import (
    EstadoPago,
    Pasarela,
    ProveedorId,
    Region,
    TrabajoId,
)
from app.infrastructure.adapters.pasarela_mercadopago import PasarelaMercadoPago
from app.infrastructure.adapters.pasarela_stripe import PasarelaStripe
from app.infrastructure.adapters.regla_brasil import ReglaBrasil
from app.infrastructure.adapters.regla_colombia import ReglaColombia


# ---------------------------------------------------------------------------
# Fakes en memoria de los puertos (mismo estilo que test_compensar.py)
# ---------------------------------------------------------------------------


class _PagoRepositorioFalso(IPagoRepository):
    def __init__(self) -> None:
        self._pagos: dict[uuid.UUID, Pago] = {}

    def guardar(self, pago: Pago) -> None:
        self._pagos[pago.id] = pago

    def obtener_por_id(self, id):
        return self._pagos.get(id.valor)

    def listar_por_trabajo(self, trabajo_id):
        raise NotImplementedError


class _RegistroTrabajosRepositorioFalso(IRegistroTrabajosRepository):
    def __init__(self) -> None:
        self._registros: dict[uuid.UUID, RegistroTrabajoElegible] = {}

    def guardar(self, registro: RegistroTrabajoElegible) -> None:
        self._registros[registro.trabajo_id.valor] = registro

    def obtener_por_trabajo(self, trabajo_id: TrabajoId):
        return self._registros.get(trabajo_id.valor)


# ---------------------------------------------------------------------------
# Espías delgados sobre las implementaciones REALES (Strategy/Adapter) — solo
# registran si fueron invocadas, no cambian el comportamiento.
# ---------------------------------------------------------------------------


class _ReglaColombiaEspia(ReglaColombia):
    def __init__(self) -> None:
        super().__init__()
        self.invocada = False

    def validar(self, pago: Pago) -> None:
        self.invocada = True
        super().validar(pago)


class _ReglaBrasilEspia(ReglaBrasil):
    def __init__(self) -> None:
        super().__init__()
        self.invocada = False

    def validar(self, pago: Pago) -> None:
        self.invocada = True
        super().validar(pago)


class _PasarelaStripeEspia(PasarelaStripe):
    def __init__(self) -> None:
        super().__init__(base_url="http://mock-stripe.invalid")
        self.invocada = False

    async def cobrar(self, pago: Pago):
        self.invocada = True
        return await super().cobrar(pago)


class _PasarelaMercadoPagoEspia(PasarelaMercadoPago):
    def __init__(self) -> None:
        super().__init__(base_url="http://mock-mercadopago.invalid")
        self.invocada = False

    async def cobrar(self, pago: Pago):
        self.invocada = True
        return await super().cobrar(pago)


# ---------------------------------------------------------------------------
# Fakes de httpx — ninguna llamada de red real; solo simulan la respuesta
# exitosa del mock externo (Stripe/MercadoPago).
# ---------------------------------------------------------------------------


class _RespuestaHttpFalsa:
    def __init__(self, datos: dict) -> None:
        self._datos = datos

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._datos


class _ClienteHttpFalso:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_ClienteHttpFalso":
        return self

    async def __aexit__(self, *args, **kwargs) -> bool:
        return False

    async def post(
        self, url: str, json: dict | None = None, **_
    ) -> _RespuestaHttpFalsa:
        if "charges" in url:
            return _RespuestaHttpFalsa({"id": "ch_test_123"})
        return _RespuestaHttpFalsa({"id": "mp_test_456"})


@pytest.fixture(autouse=True)
def _sin_red_real(monkeypatch):
    """Reemplaza httpx.AsyncClient por el fake — ambos adaptadores hacen
    `import httpx` dentro del método `cobrar`, así que basta con parchar el
    atributo del módulo real (mismo objeto en `sys.modules`)."""
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _ClienteHttpFalso)


# ---------------------------------------------------------------------------
# Prueba principal: mismo comando, mismos diccionarios inyectados, dos
# regiones distintas resueltas por dict — sin tocar código entre una región
# y otra.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagar_trabajo_resuelve_colombia_y_brasil_por_diccionario():
    pago_repo = _PagoRepositorioFalso()
    registro_repo = _RegistroTrabajosRepositorioFalso()

    regla_colombia = _ReglaColombiaEspia()
    regla_brasil = _ReglaBrasilEspia()
    pasarela_stripe = _PasarelaStripeEspia()
    pasarela_mercadopago = _PasarelaMercadoPagoEspia()

    reglas_regionales = {
        Region.COLOMBIA: regla_colombia,
        Region.BRASIL: regla_brasil,
    }
    pasarelas = {
        Pasarela.STRIPE.value: pasarela_stripe,
        Pasarela.MERCADOPAGO.value: pasarela_mercadopago,
    }

    comando = PagarTrabajo(pago_repo, registro_repo, reglas_regionales, pasarelas)

    # --- Caso Colombia: debe resolver ReglaColombia + PasarelaStripe ---
    trabajo_co = TrabajoId.nueva()
    registro_repo.guardar(
        RegistroTrabajoElegible(
            trabajo_id=trabajo_co,
            proveedor_id=ProveedorId("prov-co-1"),
            monto=Decimal("100000"),
            moneda="COP",
            region=Region.COLOMBIA,
        )
    )

    pago_id_co = await comando.ejecutar(str(trabajo_co.valor), Pasarela.STRIPE.value)

    assert regla_colombia.invocada is True
    assert regla_brasil.invocada is False
    assert pasarela_stripe.invocada is True
    assert pasarela_mercadopago.invocada is False

    # Verificamos directamente en el repo interno (fake) que el pago quedó
    # exitoso, usando la referencia devuelta por `ejecutar` (CQS: retorna
    # solo el id).
    pago_guardado_co = pago_repo._pagos[pago_id_co]
    assert pago_guardado_co.estado == EstadoPago.EXITOSO
    assert pago_guardado_co.region == Region.COLOMBIA
    assert pago_guardado_co.pasarela == Pasarela.STRIPE

    # --- Caso Brasil: MISMOS diccionarios, MISMA instancia de comando ---
    trabajo_br = TrabajoId.nueva()
    registro_repo.guardar(
        RegistroTrabajoElegible(
            trabajo_id=trabajo_br,
            proveedor_id=ProveedorId("prov-br-1"),
            monto=Decimal("1000"),
            moneda="BRL",
            region=Region.BRASIL,
        )
    )

    pago_id_br = await comando.ejecutar(
        str(trabajo_br.valor), Pasarela.MERCADOPAGO.value
    )

    assert regla_brasil.invocada is True
    assert pasarela_mercadopago.invocada is True
    # Colombia no se vuelve a tocar por el segundo `ejecutar` (siguen en True
    # desde el primer caso, no se resetean) — lo relevante es que Brasil se
    # resolvió sin que nadie modificara `PagarTrabajo` ni las clases de
    # Colombia entre un caso y el otro.

    pago_guardado_br = pago_repo._pagos[pago_id_br]
    assert pago_guardado_br.estado == EstadoPago.EXITOSO
    assert pago_guardado_br.region == Region.BRASIL
    assert pago_guardado_br.pasarela == Pasarela.MERCADOPAGO


@pytest.mark.asyncio
async def test_pagar_trabajo_trabajo_no_encontrado():
    pago_repo = _PagoRepositorioFalso()
    registro_repo = _RegistroTrabajosRepositorioFalso()
    comando = PagarTrabajo(pago_repo, registro_repo, {}, {})

    with pytest.raises(TrabajoNoEncontrado):
        await comando.ejecutar(str(uuid.uuid4()), Pasarela.STRIPE.value)


def test_pagar_trabajo_no_tiene_condicionales_por_pais():
    """Inspección estática de `pagar_trabajo.py`: el despacho por región y
    por pasarela debe ser puramente por `dict.get(...)` (puertos inyectados
    en el constructor), nunca por un `if`/`match` que compare contra un
    literal de país como "BR"/"CO"/Region.BRASIL/Region.COLOMBIA."""
    codigo_fuente = inspect.getsource(pagar_trabajo_module)

    literales_prohibidos = {"BR", "CO", "BRASIL", "COLOMBIA"}

    arbol = ast.parse(codigo_fuente)

    condicionales = [
        nodo
        for nodo in ast.walk(arbol)
        if isinstance(nodo, (ast.If,) + ((ast.Match,) if hasattr(ast, "Match") else ()))
    ]

    for nodo in condicionales:
        for sub in ast.walk(nodo):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                assert sub.value not in literales_prohibidos, (
                    f"Se encontró un condicional comparando contra el literal "
                    f"de país {sub.value!r} en pagar_trabajo.py — viola "
                    f"MOD-02 (el despacho debe ser por diccionario, no por "
                    f"if/match)."
                )
            if isinstance(sub, ast.Attribute) and sub.attr in literales_prohibidos:
                pytest.fail(
                    f"Se encontró un condicional comparando contra "
                    f"Region.{sub.attr} en pagar_trabajo.py — viola MOD-02."
                )

    # Redundancia textual simple, por si el AST no captura algún caso raro
    # (ej. comparación dentro de una comprensión anidada).
    for literal in ('"BR"', "'BR'", '"CO"', "'CO'", "Region.BRASIL", "Region.COLOMBIA"):
        assert literal not in codigo_fuente, (
            f"pagar_trabajo.py contiene el literal {literal} — revisar si "
            f"es un condicional por país que viola MOD-02."
        )
