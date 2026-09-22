"""Pruebas del `ThrottlerCrm` (DISP-02, Sidecar hacia el CRM "Gestión de
Agentes") con fakes en memoria — sin HTTP real, sin Postgres real. No es la
prueba de carga completa (esa la hace `experimento-runner` contra el mock
real del CRM); esto solo demuestra el mecanismo: (1) encolar no bloquea y
una entrega exitosa marca ENTREGADA, (2) agotar los reintentos configurados
marca AGOTADA en vez de perder la Novedad en silencio."""

import asyncio
import uuid

import pytest

from app.integraciones_externas.application.ports.gestion_agentes import (
    IGestionAgentesPort,
    ResultadoEnvioWebhook,
)
from app.novedades.domain.fabrica import FabricaNovedad
from app.novedades.domain.novedad import Novedad
from app.novedades.domain.repository import INovedadRepository
from app.novedades.domain.value_objects import EstadoNovedad, NovedadId
from app.ciclo_vida.domain.value_objects import TrabajoId
from app.integraciones_externas.infrastructure.messaging.throttler import ThrottlerCrm


class _RepoNovedadFalso(INovedadRepository):
    def __init__(self) -> None:
        self._por_id: dict[uuid.UUID, Novedad] = {}

    def guardar(self, novedad: Novedad) -> None:
        self._por_id[novedad.id] = novedad

    def obtener_por_id(self, id: NovedadId) -> Novedad | None:
        return self._por_id.get(id.valor)

    def listar_pendientes(self) -> list[Novedad]:
        return [n for n in self._por_id.values() if n.estado == EstadoNovedad.PENDIENTE]


class _CrmSiempreExitoso(IGestionAgentesPort):
    async def enviar_webhook(self, novedad: Novedad) -> ResultadoEnvioWebhook:
        return ResultadoEnvioWebhook(exitoso=True)


class _CrmSiempreRateLimitado(IGestionAgentesPort):
    """Simula un CRM que siempre responde 429 con Retry-After — igual que
    `AdaptadorGestionAgentesHttp` reportaría un 429 real."""

    def __init__(self) -> None:
        self.llamadas = 0

    async def enviar_webhook(self, novedad: Novedad) -> ResultadoEnvioWebhook:
        self.llamadas += 1
        return ResultadoEnvioWebhook(
            exitoso=False, motivo_falla="rate_limited_429", reintentar_despues_s=0.001
        )


def _novedad() -> Novedad:
    return FabricaNovedad.crear(
        trabajo_id=TrabajoId(uuid.uuid4()), descripcion="novedad de prueba"
    )


async def _esperar_estado(
    repo: _RepoNovedadFalso, novedad_id: uuid.UUID, estado: EstadoNovedad
) -> Novedad | None:
    for _ in range(300):
        guardada = repo.obtener_por_id(NovedadId(novedad_id))
        if guardada is not None and guardada.estado == estado:
            return guardada
        await asyncio.sleep(0.01)
    return repo.obtener_por_id(NovedadId(novedad_id))


@pytest.mark.asyncio
async def test_encolar_no_bloquea_y_una_entrega_exitosa_marca_entregada():
    repo = _RepoNovedadFalso()
    throttler = ThrottlerCrm(
        puerto_crm=_CrmSiempreExitoso(),
        repo=repo,
        tasa_rps=1000,
        tamano_cola=10,
        max_reintentos=3,
        backoff_base_s=0.001,
        backoff_max_s=0.01,
    )
    novedad = _novedad()

    throttler.iniciar()
    # encolar() no debe tardar en retornar -- no ejecuta ninguna llamada de
    # red, solo `await queue.put(...)`.
    await asyncio.wait_for(throttler.encolar(novedad), timeout=0.1)

    guardada = await _esperar_estado(repo, novedad.id, EstadoNovedad.ENTREGADA)
    await throttler.detener()

    assert guardada is not None
    assert guardada.estado == EstadoNovedad.ENTREGADA
    assert guardada.intentos == 1


@pytest.mark.asyncio
async def test_agota_reintentos_en_vez_de_perder_la_novedad_en_silencio():
    repo = _RepoNovedadFalso()
    crm = _CrmSiempreRateLimitado()
    throttler = ThrottlerCrm(
        puerto_crm=crm,
        repo=repo,
        tasa_rps=1000,
        tamano_cola=10,
        max_reintentos=3,
        backoff_base_s=0.001,
        backoff_max_s=0.01,
    )
    novedad = _novedad()

    throttler.iniciar()
    await throttler.encolar(novedad)

    guardada = await _esperar_estado(repo, novedad.id, EstadoNovedad.AGOTADA)
    await throttler.detener()

    assert guardada is not None
    assert guardada.estado == EstadoNovedad.AGOTADA
    assert guardada.intentos == 3
    assert crm.llamadas == 3
