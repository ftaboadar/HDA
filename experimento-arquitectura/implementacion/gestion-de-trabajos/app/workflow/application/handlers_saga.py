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
                secuencia=i + 2,
                tipo="COMANDO_ENVIADO",
                mensaje=cmd.__class__.__name__,
                id_mensaje=getattr(cmd, "comando_id", None),
                payload=cmd.__dict__,
            )

    async def handle_franja_reservada(self, payload: dict, id_mensaje: str):
        if self.es_mensaje_duplicado(id_mensaje):
            logger.info(f"Mensaje {id_mensaje} ya procesado. Ignorando.")
            return

        trabajo_id = uuid.UUID(payload["correlation_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        trabajo = self.repo_trabajos.obtener_por_id(TrabajoId(trabajo_id))
        if not saga or not trabajo:
            logger.error(f"Saga o trabajo no encontrado para trabajo {trabajo_id}")
            return
        comandos = self.coordinador.on_franja_reservada(
            saga=saga,
            trabajo=trabajo,
            proveedor_id=payload["proveedor_id"],
            reserva_id=payload["reserva_id"],
            monto=payload["monto"],
            moneda=payload.get("moneda", "COP"),
        )
        await self._procesar_y_publicar(
            saga, trabajo, comandos, "AgendaConfirmada", payload, id_mensaje
        )

    async def handle_proveedor_seleccionado(self, payload: dict, id_mensaje: str):
        """Paso 3 (§7.1): el canal del origen (Marketplace/Siniestros/
        Suscripciones) elige al proveedor y publica `ProveedorSeleccionado`
        en su propio namespace -- GT responde con el comando `ReservarFranja`
        a Proveedores·Agenda (A14). `on_proveedor_seleccionado` en
        `coordinador.py` ya armaba ese comando; antes de este fix no existía
        ningún handler que lo invocara, así que nunca se enviaba.

        Nota de payload: a diferencia de los demás handlers de esta clase,
        aquí se busca la saga por `payload["trabajo_id"]`, no por
        `payload["correlation_id"]` -- así lo trae el contrato de
        `ProveedorSeleccionado` en el catálogo (§7)."""
        if self.es_mensaje_duplicado(id_mensaje):
            logger.info(f"Mensaje {id_mensaje} ya procesado. Ignorando.")
            return

        trabajo_id = uuid.UUID(payload["trabajo_id"])
        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        if not saga:
            logger.error(f"Saga no encontrada para trabajo {trabajo_id}")
            return

        franja = payload.get("franja") or {}
        comandos = self.coordinador.on_proveedor_seleccionado(
            saga=saga,
            proveedor_id=payload["proveedor_id"],
            tecnico_id=payload["tecnico_id"],
            fecha_franja=franja.get("fecha", ""),
            bloque=franja.get("bloque", ""),
        )
        await self._procesar_y_publicar(
            saga, None, comandos, "ProveedorSeleccionado", payload, id_mensaje
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
            sagas_activas = (
                sesion.query(SagaInstanciaORM)
                .filter(SagaInstanciaORM.estado == "INICIADA")
                .all()
            )

            for saga_orm in sagas_activas:
                paso = saga_orm.paso_actual
                if paso in plazos:
                    limite_minutos = plazos[paso]
                    tiempo_transcurrido = ahora - saga_orm.actualizada_en
                    if tiempo_transcurrido > timedelta(minutes=limite_minutos):
                        # Expirado
                        logger.warning(
                            f"Saga {saga_orm.saga_id} expiró en el paso {paso}"
                        )
                        saga = self.repo_saga.obtener_por_id(saga_orm.saga_id)
                        trabajo = self.repo_trabajos.obtener_por_id(saga.trabajo_id)

                        # Guardar expiración en el log
                        self.repo_saga.guardar(
                            saga,
                            tipo="PASO_EXPIRADO",
                            mensaje=f"Expiró en el paso {paso}",
                            payload={},
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
                            payload={},
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

    async def handle_completar_sub_trabajo(
        self, trabajo_id: uuid.UUID, id_mensaje: str
    ):
        """Paso 5 (§7.1 y §5.1 paso 5): 'Proveedor -API-> GT: CompletarSubTrabajo
        -> Motor -async SubTrabajosCompletos-> Ciclo de Vida: CerrarTrabajo
        (FINALIZADO)'. Disparado por `POST /trabajos/{id}/completar` (no por
        un mensaje de Pulsar) -- por eso recibe `trabajo_id` directo en vez
        de un `payload` de evento, pero sigue el mismo patrón de idempotencia
        y saga log que los demás handlers (ver
        `application/commands/completar_sub_trabajo.py`, que es quien genera
        el `id_mensaje` para esta llamada).

        Decisión sobre `pago_id` (tarea 4): no se agregó columna nueva a
        `SagaInstancia`/`Trabajo` -- se lee del último `EVENTO_RECIBIDO` de
        tipo `PagoRetenido` en el Saga Log (`obtener_pago_id_retenido`), que
        ya lo guarda `handle_pago_retenido` en su payload."""
        if self.es_mensaje_duplicado(id_mensaje):
            logger.info(f"Mensaje {id_mensaje} ya procesado. Ignorando.")
            return

        saga = self.repo_saga.obtener_por_trabajo_id(trabajo_id)
        trabajo = self.repo_trabajos.obtener_por_id(TrabajoId(trabajo_id))
        if not saga or not trabajo:
            logger.error(f"Saga o trabajo no encontrado para trabajo {trabajo_id}")
            return

        pago_id = self.repo_saga.obtener_pago_id_retenido(saga.id) or ""
        comandos = self.coordinador.on_trabajo_completado_por_proveedor(
            saga, trabajo, pago_id
        )
        await self._procesar_y_publicar(
            saga,
            trabajo,
            comandos,
            "CompletarSubTrabajo",
            {"trabajo_id": str(trabajo_id), "pago_id": pago_id},
            id_mensaje,
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
