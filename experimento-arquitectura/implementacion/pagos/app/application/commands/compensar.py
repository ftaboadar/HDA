import asyncio
import uuid
from app.domain.pagos.repository import IPagoRepository
from app.domain.pagos.value_objects import PagoId, TrabajoId
from app.seedwork.infraestructura.pulsar.mensajeria import PublicadorPulsar
from app.common.logging_utils import configurar_logging

logger = configurar_logging("application.commands.compensar_pago")


class CompensarPago:
    def __init__(self, pago_repo: IPagoRepository, publicador: PublicadorPulsar):
        self._pago_repo = pago_repo
        self._publicador = publicador

    async def ejecutar(self, trabajo_id: str) -> None:
        pagos = await asyncio.to_thread(
            self._pago_repo.obtener_por_trabajo, TrabajoId.desde_str(trabajo_id)
        )
        if not pagos:
            logger.warning(
                f"No se encontró pago para trabajo {trabajo_id} al compensar"
            )
            return

        pago = pagos[0]

        # En la realidad llamamos a la pasarela externa para hacer el refund.
        # Aquí simulamos y registramos la transaccion y el evento en Outbox.
        from app.infrastructure.persistence.models_db import TransaccionORM, OutboxEventORM
        from app.common.db import SessionLocal
        import json

        outbox_event = OutboxEventORM(
            topic="hda/pagos/pago.compensado",
            event_type="PagoCompensado",
            payload=json.dumps({"pago_id": str(pago.id), "trabajo_id": trabajo_id}),
            correlation_id=trabajo_id,
            published="FALSE"
        )

        with SessionLocal() as db:
            tx = TransaccionORM(pago_id=pago.id, tipo="COMPENSACION", estado="EXITOSA")
            db.add(tx)
            db.add(outbox_event)
            db.commit()

        pago.estado = "COMPENSADO"
        await asyncio.to_thread(self._pago_repo.guardar, pago)


class PagoNoEncontrado(Exception):
    pass


class Compensar:
    def __init__(self, pago_repo: IPagoRepository) -> None:
        self._pago_repo = pago_repo

    async def ejecutar(self, pago_id: str) -> uuid.UUID:
        pago = await asyncio.to_thread(
            self._pago_repo.obtener_por_id, PagoId.desde_str(pago_id)
        )
        if pago is None:
            raise PagoNoEncontrado(pago_id)

        pago.compensar()
        await asyncio.to_thread(self._pago_repo.guardar, pago)

        from app.application.dispatcher_eventos_dominio import despachar

        await despachar(pago.recoger_eventos())

        from app.common.logging_utils import log_evento

        log_evento(
            logger,
            "pago_compensado",
            comando="Compensar",
            agregado="Pago",
            pago_id=pago_id,
            trabajo_id=str(pago.trabajo_id),
            estado=pago.estado.value,
            paso_de_saga="compensacion",
        )
        return pago.id
