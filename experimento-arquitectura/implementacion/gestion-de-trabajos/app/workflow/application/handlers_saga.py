import uuid
import logging

from app.workflow.infrastructure.persistence.saga_repository_sqlalchemy import (
    SagaRepositorySQLAlchemy,
)
from app.ciclo_vida.infrastructure.persistence.trabajo_repository_sqlalchemy import (
    TrabajoRepositorySQLAlchemy,
)
from app.infrastructure.messaging.publicador_pulsar import PublicadorPulsar
from app.workflow.domain.coordinador import CoordinadorSaga
from app.ciclo_vida.domain.value_objects import TrabajoId
from app.common.db import SessionLocal
from app.infrastructure.persistence.models_db import SagaLogORM

logger = logging.getLogger(__name__)

class SagaHandlers:
    def __init__(
        self,
        repo_saga: SagaRepositorySQLAlchemy,
        repo_trabajos: TrabajoRepositorySQLAlchemy,
        publicador: PublicadorPulsar,
    ):
        self.repo_saga = repo_saga
        self.repo_trabajos = repo_trabajos
        self.publicador = publicador
        self.coordinador = CoordinadorSaga()

    def es_mensaje_duplicado(self, id_mensaje: str) -> bool:
        if not id_mensaje:
            return False
        with SessionLocal() as sesion:
            existe = sesion.query(SagaLogORM).filter_by(id_mensaje=id_mensaje).first()
            return existe is not None

    async def _procesar_y_publicar(
        self, saga, trabajo, comandos, mensaje_nombre, payload, id_mensaje: str
    ):
        if trabajo:
            self.repo_trabajos.guardar(trabajo)
            
        # 1. Guardar evento recibido
        self.repo_saga.guardar(
            saga,
            tipo="EVENTO_RECIBIDO",
            mensaje=mensaje_nombre,
            id_mensaje=id_mensaje,
            payload=payload,
        )

        # 2. Publicar y guardar comandos enviados
        for i, cmd in enumerate(comandos):
            await self.publicador.publicar_comando(cmd)
            self.repo_saga.guardar(
                saga,
                secuencia=i+2,
                tipo="COMANDO_ENVIADO",
                mensaje=cmd.__class__.__name__,
                id_mensaje=getattr(cmd, "comando_id", None),
                payload=cmd.__dict__
            )

    async def handle_franja_reservada(self, payload: dict, id_mensaje: str):
        if self.es_mensaje_duplicado(id_mensaje):
            logger.info(f"Mensaje {id_mensaje} ya procesado. Ignorando.")
            return

        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        if not saga:
            logger.error(f"Saga no encontrada para trabajo {trabajo_id}")
            return
        comandos = self.coordinador.on_franja_reservada(
            saga=saga,
            reserva_id=payload["reserva_id"],
            monto=payload["monto"],
            moneda=payload.get("moneda", "COP"),
        )
        await self._procesar_y_publicar(
            saga, None, comandos, "AgendaConfirmada", payload, id_mensaje
        )

    async def handle_franja_rechazada(self, payload: dict, id_mensaje: str):
        if self.es_mensaje_duplicado(id_mensaje):
            return

        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        if not saga:
            return
        comandos = self.coordinador.on_franja_rechazada(
            saga=saga,
            origen=payload.get("origen", "proveedor"),
            origen_id=payload.get("origen_id", "0"),
        )
        await self._procesar_y_publicar(
            saga, None, comandos, "AgendaRechazada", payload, id_mensaje
        )

    async def handle_pago_retenido(self, payload: dict, id_mensaje: str):
        if self.es_mensaje_duplicado(id_mensaje):
            return

        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        trabajo = self.repo_trabajos.obtener_por_id(TrabajoId(trabajo_id))
        if not saga or not trabajo:
            return
        comandos = self.coordinador.on_pago_retenido(saga, trabajo)
        await self._procesar_y_publicar(
            saga, trabajo, comandos, "PagoRetenido", payload, id_mensaje
        )

    async def handle_pago_retencion_fallida(self, payload: dict, id_mensaje: str):
        if self.es_mensaje_duplicado(id_mensaje):
            return

        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        trabajo = self.repo_trabajos.obtener_por_id(TrabajoId(trabajo_id))
        if not saga or not trabajo:
            return
        comandos = self.coordinador.on_pago_retencion_fallida(
            saga, trabajo, payload.get("reserva_id", "")
        )
        await self._procesar_y_publicar(
            saga, trabajo, comandos, "PagoRetencionFallida", payload, id_mensaje
        )

    async def check_deadlines(self):
        from datetime import datetime, timezone, timedelta
        from app.workflow.domain.value_objects import PasoSaga
        
        # Plazos arbitrarios para este POC
        plazos = {
            PasoSaga.PUBLICAR_ELEGIBLES.value: 5,  # 5 minutos
            PasoSaga.RESERVAR_FRANJA.value: 2,
            PasoSaga.RETENER_PAGO.value: 5,
        }
        
        with SessionLocal() as sesion:
            from app.infrastructure.persistence.models_db import SagaInstanciaORM
            ahora = datetime.now(timezone.utc)
            sagas_activas = sesion.query(SagaInstanciaORM).filter(
                SagaInstanciaORM.estado == "INICIADA"
            ).all()
            
            for saga_orm in sagas_activas:
                paso = saga_orm.paso_actual
                if paso in plazos:
                    limite_minutos = plazos[paso]
                    tiempo_transcurrido = ahora - saga_orm.actualizada_en
                    if tiempo_transcurrido > timedelta(minutes=limite_minutos):
                        # Expirado
                        logger.warning(f"Saga {saga_orm.saga_id} expiró en el paso {paso}")
                        saga = self.repo_saga.obtener_por_id(saga_orm.saga_id)
                        trabajo = self.repo_trabajos.obtener_por_id(saga.trabajo_id)
                        
                        # Guardar expiración en el log
                        self.repo_saga.guardar(
                            saga,
                            tipo="PASO_EXPIRADO",
                            mensaje=f"Expiró en el paso {paso}",
                            payload={}
                        )
                        
                        # Ejecutar compensación genérica (ejemplo: cancelar)
                        if trabajo:
                            try:
                                trabajo.cancelar()
                                self.repo_trabajos.guardar(trabajo)
                            except Exception as e:
                                logger.error(f"Error cancelando trabajo: {e}")
                        
                        saga.compensar()
                        self.repo_saga.guardar(
                            saga,
                            tipo="SAGA_COMPENSADA",
                            mensaje="Saga compensada por timeout",
                            payload={}
                        )

    async def handle_pago_liberado(self, payload: dict, id_mensaje: str):
        if self.es_mensaje_duplicado(id_mensaje):
            return

        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        trabajo = self.repo_trabajos.obtener_por_id(TrabajoId(trabajo_id))
        if not saga or not trabajo:
            return
        
        # Ocurre como respuesta al paso 6
        self.coordinador.on_pago_liberado(saga, trabajo)
        await self._procesar_y_publicar(
            saga, trabajo, [], "PagoLiberado", payload, id_mensaje
        )

    async def handle_pago_compensado(self, payload: dict, id_mensaje: str):
        if self.es_mensaje_duplicado(id_mensaje):
            return

        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        trabajo = self.repo_trabajos.obtener_por_id(TrabajoId(trabajo_id))
        if not saga or not trabajo:
            return
        
        self.coordinador.on_pago_compensado(saga, trabajo)
        await self._procesar_y_publicar(
            saga, trabajo, [], "PagoCompensado", payload, id_mensaje
        )
