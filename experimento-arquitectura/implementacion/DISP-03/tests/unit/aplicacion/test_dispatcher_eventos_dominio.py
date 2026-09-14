"""Prueba de regresión para el bug de producción encontrado en GCP
(2026-09-06): `PublicadorPubSub.publicar_evento`/`publicar_fallida` pueden
lanzar RuntimeError si el topic no está configurado (o cualquier otro error
de transporte transitorio) — despachar() NO debe dejar que eso se propague,
porque el estado del agregado ya se persistió con éxito antes de llegar
aquí, y worker/push_handler.py depende de que esta capa nunca reviente para
poder garantizar su "siempre respondemos 200" (ver docstring de ese
módulo)."""

import pytest

from app.application.dispatcher_eventos_dominio import despachar
from app.domain.verificacion.eventos import VerificacionAgotoReintentos, VerificacionCompletada
from app.domain.verificacion.fabrica import FabricaVerificacion
from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.value_objects import ProveedorId, TipoVerificador, VerificacionId
from app.domain.verificacion.verificacion import Verificacion


class RepositorioEnMemoria(IVerificacionRepository):
    def __init__(self) -> None:
        self._filas: dict = {}

    def guardar(self, verificacion: Verificacion) -> None:
        self._filas[verificacion.id] = verificacion

    def obtener_por_id(self, id):
        return self._filas.get(id.valor)

    def listar_por_proveedor(self, proveedor_id: ProveedorId) -> list[Verificacion]:
        return [v for v in self._filas.values() if v.proveedor_id == proveedor_id]

    def listar_en_dlq(self) -> list[Verificacion]:
        return [v for v in self._filas.values() if v.estado.value == "FALLIDA_DLQ"]

    def listar(self, estado=None, proveedor_id=None) -> list[Verificacion]:
        return list(self._filas.values())


class PublicadorQueSiempreFalla:
    """Doble de prueba equivalente a PublicadorPubSub sin
    PUBSUB_TOPIC_SOLICITUDES configurado: cualquier publish lanza."""

    async def publicar_solicitud(self, mensaje: dict) -> None:
        raise RuntimeError("PUBSUB_TOPIC_SOLICITUDES no configurado")

    async def publicar_fallida(self, mensaje: dict) -> None:
        raise RuntimeError("fallo de transporte simulado (DLQ)")

    async def publicar_evento(self, routing_key: str, mensaje: dict) -> None:
        raise RuntimeError("PUBSUB_TOPIC_SOLICITUDES no configurado")


@pytest.mark.asyncio
async def test_despachar_no_propaga_si_falla_publicar_evento_proveedor_habilitado():
    repo = RepositorioEnMemoria()
    proveedor = ProveedorId("prov-resiliencia-1")
    verificacion = FabricaVerificacion.crear(proveedor, TipoVerificador.POLICIA)
    repo.guardar(verificacion)

    evento = VerificacionCompletada(
        verificacion_id=VerificacionId(verificacion.id), proveedor_id=proveedor
    )

    # No debe lanzar RuntimeError aunque el publicador falle: el estado del
    # agregado ya está persistido; la publicación es un efecto secundario.
    await despachar([evento], repo, PublicadorQueSiempreFalla())


@pytest.mark.asyncio
async def test_despachar_no_propaga_si_falla_publicar_fallida_dlq():
    repo = RepositorioEnMemoria()
    proveedor = ProveedorId("prov-resiliencia-2")
    verificacion = FabricaVerificacion.crear(proveedor, TipoVerificador.RUES)
    repo.guardar(verificacion)

    evento = VerificacionAgotoReintentos(
        verificacion_id=VerificacionId(verificacion.id),
        proveedor_id=proveedor,
        motivo_falla="reintentos agotados",
    )

    await despachar([evento], repo, PublicadorQueSiempreFalla())
