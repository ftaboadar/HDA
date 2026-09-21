import uuid
import logging
from typing import Dict, Any

from app.infrastructure.persistence.saga_repository_sqlalchemy import SagaRepositorySQLAlchemy
from app.infrastructure.persistence.trabajo_repository_sqlalchemy import TrabajoRepositorySQLAlchemy
from app.infrastructure.messaging.publicador_pulsar import PublicadorPulsar
from app.domain.workflow.coordinador import CoordinadorSaga
from app.domain.ciclo_vida.value_objects import TrabajoId

logger = logging.getLogger(__name__)

class SagaHandlers:
    def __init__(self, repo_saga: SagaRepositorySQLAlchemy, repo_trabajos: TrabajoRepositorySQLAlchemy, publicador: PublicadorPulsar):
        self.repo_saga = repo_saga
        self.repo_trabajos = repo_trabajos
        self.publicador = publicador
        self.coordinador = CoordinadorSaga()

    async def _procesar_y_publicar(self, saga, trabajo, comandos, evento_nombre, payload):
        self.repo_saga.guardar(saga, evento_log=evento_nombre, detalles_log=payload)
        if trabajo:
            self.repo_trabajos.guardar(trabajo)
        for cmd in comandos:
            await self.publicador.publicar_comando(cmd)

    async def handle_franja_reservada(self, payload: dict):
        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        if not saga:
            logger.error(f"Saga no encontrada para trabajo {trabajo_id}")
            return
        comandos = self.coordinador.on_franja_reservada(
            saga=saga,
            reserva_id=payload["reserva_id"],
            monto=payload["monto"],
            moneda=payload.get("moneda", "COP")
        )
        await self._procesar_y_publicar(saga, None, comandos, "FranjaReservada", payload)

    async def handle_franja_rechazada(self, payload: dict):
        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        if not saga:
            return
        comandos = self.coordinador.on_franja_rechazada(
            saga=saga,
            origen=payload.get("origen", "proveedor"),
            origen_id=payload.get("origen_id", "0")
        )
        await self._procesar_y_publicar(saga, None, comandos, "FranjaRechazada", payload)

    async def handle_pago_retenido(self, payload: dict):
        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        trabajo = self.repo_trabajos.obtener_por_id(TrabajoId(trabajo_id))
        if not saga or not trabajo:
            return
        comandos = self.coordinador.on_pago_retenido(saga, trabajo)
        await self._procesar_y_publicar(saga, trabajo, comandos, "PagoRetenido", payload)

    async def handle_pago_retencion_fallida(self, payload: dict):
        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        trabajo = self.repo_trabajos.obtener_por_id(TrabajoId(trabajo_id))
        if not saga or not trabajo:
            return
        comandos = self.coordinador.on_pago_retencion_fallida(saga, trabajo, payload.get("reserva_id", ""))
        await self._procesar_y_publicar(saga, trabajo, comandos, "PagoRetencionFallida", payload)
