"""Pruebas del dispatcher de eventos de dominio (Regla 5, criterio 4) — con
fakes en memoria, sin BD/Pulsar/HTTP real. Verifica la reacción intra-
servicio (Pagos se entera de un `TrabajoFinalizado` sin tocar
`ITrabajoRepository`) y que un fallo al publicar el evento de integración
no se propaga."""

import uuid
from decimal import Decimal

import pytest

from app.application.dispatcher_eventos_dominio import despachar
from app.application.ports.registro_trabajos import RegistroTrabajoElegible
from app.domain.trabajo.eventos import TrabajoFinalizado
from app.domain.trabajo.value_objects import ProveedorId, Region, TrabajoId


class _PublicadorFalso:
    def __init__(self, falla: bool = False) -> None:
        self.falla = falla
        self.eventos_publicados: list[TrabajoFinalizado] = []

    async def publicar_trabajo_finalizado(self, evento: TrabajoFinalizado) -> None:
        if self.falla:
            raise RuntimeError("Pulsar caído (simulado)")
        self.eventos_publicados.append(evento)


class _RegistroTrabajosRepositorioFalso:
    def __init__(self) -> None:
        self._por_trabajo: dict[TrabajoId, RegistroTrabajoElegible] = {}

    def guardar(self, registro: RegistroTrabajoElegible) -> None:
        self._por_trabajo[registro.trabajo_id] = registro

    def obtener_por_trabajo(
        self, trabajo_id: TrabajoId
    ) -> RegistroTrabajoElegible | None:
        return self._por_trabajo.get(trabajo_id)


def _evento_trabajo_finalizado() -> TrabajoFinalizado:
    return TrabajoFinalizado(
        trabajo_id=TrabajoId(uuid.uuid4()),
        proveedor_id=ProveedorId("prov-1"),
        monto=Decimal(100000),
        moneda="COP",
        region=Region.COLOMBIA,
    )


@pytest.mark.asyncio
async def test_trabajo_finalizado_puebla_el_registro_de_pagos():
    """Pagos se entera del trabajo SOLO a través del evento, nunca de
    ITrabajoRepository (el repositorio del otro módulo)."""
    registro_repo = _RegistroTrabajosRepositorioFalso()
    publicador = _PublicadorFalso()
    evento = _evento_trabajo_finalizado()

    await despachar([evento], publicador=publicador, registro_repo=registro_repo)

    registro = registro_repo.obtener_por_trabajo(evento.trabajo_id)
    assert registro is not None
    assert registro.proveedor_id == evento.proveedor_id
    assert registro.monto == evento.monto
    assert registro.region == evento.region


@pytest.mark.asyncio
async def test_trabajo_finalizado_publica_evento_de_integracion():
    registro_repo = _RegistroTrabajosRepositorioFalso()
    publicador = _PublicadorFalso()
    evento = _evento_trabajo_finalizado()

    await despachar([evento], publicador=publicador, registro_repo=registro_repo)

    assert publicador.eventos_publicados == [evento]


@pytest.mark.asyncio
async def test_fallo_al_publicar_no_impide_que_el_registro_ya_haya_quedado():
    """Defensa en profundidad: el registro intra-servicio no depende de que
    Pulsar esté arriba — mismo principio que DISP-03 (una falla de
    notificación no debe revertir lo ya persistido)."""
    registro_repo = _RegistroTrabajosRepositorioFalso()
    publicador = _PublicadorFalso(falla=True)
    evento = _evento_trabajo_finalizado()

    await despachar(
        [evento], publicador=publicador, registro_repo=registro_repo
    )  # no debe lanzar

    assert registro_repo.obtener_por_trabajo(evento.trabajo_id) is not None
