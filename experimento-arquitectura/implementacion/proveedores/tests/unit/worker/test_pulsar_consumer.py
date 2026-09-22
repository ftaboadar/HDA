"""Prueba de integración MÍNIMA (sin Pulsar/Postgres reales, ver docstring
de `app/worker/pulsar_consumer.py`) del hallazgo del 2026-09-22: hasta este
cambio no existía ningún consumidor real de `verificacion.solicitudes`, así
que `POST /verificaciones` publicaba la solicitud y ninguna verificación
salía nunca de PENDIENTE.

Esta prueba ejercita `_procesar_mensaje` de punta a punta contra el dominio
REAL (`Verificacion`, `FabricaVerificacion`, `RegistrarIntento`,
`app.application.dispatcher_eventos_dominio.despachar`) con dobles de prueba
solo en los bordes de infraestructura: el mensaje de Pulsar, el `consumer`
(ack/nack) y `VerificacionRepositorySQLAlchemy` (sustituido por el mismo
`RepositorioEnMemoria` que ya usa
`tests/unit/aplicacion/test_dispatcher_eventos_dominio.py` — no se inventa un
segundo doble). `procesar_verificacion()` (que sí llamaría a los 3 mocks
HTTP externos) se monkeypatchea para no requerir esos servicios levantados;
todo lo que pasa DESPUÉS de esa llamada (registrar cada intento, mover el
agregado a COMPLETADA/FALLIDA_DLQ, publicar el evento de integración
correspondiente, hacer ack) es código real."""

from __future__ import annotations

import json

import pytest

from app.verificacion.application.procesar_verificacion import IntentoResultado, ResultadoProceso
from app.verificacion.domain.fabrica import FabricaVerificacion
from app.verificacion.domain.repository import IVerificacionRepository
from app.verificacion.domain.value_objects import (
    EstadoVerificacion,
    ProveedorId,
    ResultadoIntento,
    TipoVerificador,
    VerificacionId,
)
from app.verificacion.domain.verificacion import Verificacion
from app.worker import pulsar_consumer


class RepositorioEnMemoria(IVerificacionRepository):
    """Mismo doble que tests/unit/aplicacion/test_dispatcher_eventos_dominio.py."""

    def __init__(self) -> None:
        self._filas: dict = {}

    def guardar(self, verificacion: Verificacion) -> None:
        self._filas[verificacion.id] = verificacion

    def obtener_por_id(self, id: VerificacionId):
        return self._filas.get(id.valor)

    def listar_por_proveedor(self, proveedor_id: ProveedorId) -> list[Verificacion]:
        return [v for v in self._filas.values() if v.proveedor_id == proveedor_id]

    def listar_en_dlq(self) -> list[Verificacion]:
        return [v for v in self._filas.values() if v.estado == EstadoVerificacion.FALLIDA_DLQ]

    def listar(self, estado=None, proveedor_id=None) -> list[Verificacion]:
        return list(self._filas.values())


class PublicadorEnMemoria:
    """Doble mínimo del puerto `Publicador` — registra qué se publicó en vez
    de hablarle a un broker real, para poder aserir sobre el evento de
    INTEGRACIÓN (`proveedor.habilitado` / DLQ) sin infraestructura."""

    def __init__(self) -> None:
        self.solicitudes: list[dict] = []
        self.fallidas: list[dict] = []
        self.eventos: list[tuple[str, dict]] = []

    async def publicar_solicitud(self, mensaje: dict) -> None:
        self.solicitudes.append(mensaje)

    async def publicar_fallida(self, mensaje: dict) -> None:
        self.fallidas.append(mensaje)

    async def publicar_evento(self, routing_key: str, mensaje: dict) -> None:
        self.eventos.append((routing_key, mensaje))


class _MensajePulsarFalso:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()

    def data(self) -> bytes:
        return self._body


class _ConsumidorPulsarFalso:
    def __init__(self) -> None:
        self.acks: list[_MensajePulsarFalso] = []
        self.nacks: list[_MensajePulsarFalso] = []

    def acknowledge(self, mensaje: _MensajePulsarFalso) -> None:
        self.acks.append(mensaje)

    def negative_acknowledge(self, mensaje: _MensajePulsarFalso) -> None:
        self.nacks.append(mensaje)


def _payload_para(verificacion: Verificacion) -> dict:
    return {
        "verificacion_id": str(verificacion.id),
        "proveedor_id": str(verificacion.proveedor_id),
        "tipo_verificador": verificacion.tipo_verificador.value,
    }


@pytest.mark.asyncio
async def test_procesar_mensaje_exitoso_completa_la_verificacion_y_hace_ack(monkeypatch):
    repo = RepositorioEnMemoria()
    publicador = PublicadorEnMemoria()
    verificacion = FabricaVerificacion.crear(ProveedorId("prov-pulsar-1"), TipoVerificador.POLICIA)
    repo.guardar(verificacion)

    monkeypatch.setattr(pulsar_consumer, "VerificacionRepositorySQLAlchemy", lambda: repo)

    async def _procesar_verificacion_falso(verificacion_id, proveedor_id, tipo_verificador):
        return ResultadoProceso(
            exito=True,
            intentos=1,
            detalle_intentos=[IntentoResultado(exito=True, duracion_ms=42)],
        )

    monkeypatch.setattr(pulsar_consumer, "procesar_verificacion", _procesar_verificacion_falso)

    mensaje = _MensajePulsarFalso(_payload_para(verificacion))
    consumidor = _ConsumidorPulsarFalso()

    await pulsar_consumer._procesar_mensaje(mensaje, consumidor, publicador)

    persistida = repo.obtener_por_id(VerificacionId(verificacion.id))
    assert persistida.estado == EstadoVerificacion.COMPLETADA
    assert consumidor.acks == [mensaje]
    assert consumidor.nacks == []


@pytest.mark.asyncio
async def test_procesar_mensaje_agota_reintentos_mueve_a_dlq_y_publica_fallida(monkeypatch):
    repo = RepositorioEnMemoria()
    publicador = PublicadorEnMemoria()
    verificacion = FabricaVerificacion.crear(
        ProveedorId("prov-pulsar-2"), TipoVerificador.CERTIFICADORA
    )
    repo.guardar(verificacion)

    monkeypatch.setattr(pulsar_consumer, "VerificacionRepositorySQLAlchemy", lambda: repo)

    async def _procesar_verificacion_falso(verificacion_id, proveedor_id, tipo_verificador):
        return ResultadoProceso(
            exito=False,
            intentos=verificacion.max_intentos,
            motivo_falla="certificadora caída",
            detalle_intentos=[
                IntentoResultado(exito=False, duracion_ms=10, error="certificadora caída")
                for _ in range(verificacion.max_intentos)
            ],
        )

    monkeypatch.setattr(pulsar_consumer, "procesar_verificacion", _procesar_verificacion_falso)

    mensaje = _MensajePulsarFalso(_payload_para(verificacion))
    consumidor = _ConsumidorPulsarFalso()

    await pulsar_consumer._procesar_mensaje(mensaje, consumidor, publicador)

    persistida = repo.obtener_por_id(VerificacionId(verificacion.id))
    assert persistida.estado == EstadoVerificacion.FALLIDA_DLQ
    assert consumidor.acks == [mensaje]
    assert len(publicador.fallidas) == 1
    assert publicador.fallidas[0]["verificacion_id"] == str(verificacion.id)


@pytest.mark.asyncio
async def test_procesar_mensaje_redelivery_de_verificacion_ya_terminal_solo_hace_ack(
    monkeypatch,
):
    """Idempotencia ante redelivery de Pulsar (ver docstring del módulo): si
    la verificación ya está en un estado terminal, no se vuelve a procesar
    (evitaría chocar contra el invariante de `Verificacion.registrar_intento`,
    que solo acepta intentos en PENDIENTE) — solo se hace ack."""
    repo = RepositorioEnMemoria()
    publicador = PublicadorEnMemoria()
    verificacion = FabricaVerificacion.crear(ProveedorId("prov-pulsar-3"), TipoVerificador.RUES)
    verificacion.registrar_intento(resultado=ResultadoIntento.EXITOSO, duracion_ms=5)
    repo.guardar(verificacion)
    assert verificacion.estado == EstadoVerificacion.COMPLETADA

    monkeypatch.setattr(pulsar_consumer, "VerificacionRepositorySQLAlchemy", lambda: repo)

    llamado = {"veces": 0}

    async def _procesar_verificacion_no_deberia_llamarse(*args, **kwargs):
        llamado["veces"] += 1
        raise AssertionError("no debe reprocesar una verificación ya terminal")

    monkeypatch.setattr(
        pulsar_consumer, "procesar_verificacion", _procesar_verificacion_no_deberia_llamarse
    )

    mensaje = _MensajePulsarFalso(_payload_para(verificacion))
    consumidor = _ConsumidorPulsarFalso()

    await pulsar_consumer._procesar_mensaje(mensaje, consumidor, publicador)

    assert llamado["veces"] == 0
    assert consumidor.acks == [mensaje]


@pytest.mark.asyncio
async def test_procesar_mensaje_malformado_hace_nack_no_ack(monkeypatch):
    """Payload sin `verificacion_id` (KeyError antes de tocar el dominio) ->
    nack, no ack: es exactamente el caso que la DeadLetterPolicy NATIVA de
    Pulsar (`construir_dead_letter_policy`) existe para cubrir."""
    publicador = PublicadorEnMemoria()
    mensaje = _MensajePulsarFalso({"proveedor_id": "prov-x"})  # falta verificacion_id
    consumidor = _ConsumidorPulsarFalso()

    await pulsar_consumer._procesar_mensaje(mensaje, consumidor, publicador)

    assert consumidor.acks == []
    assert consumidor.nacks == [mensaje]
