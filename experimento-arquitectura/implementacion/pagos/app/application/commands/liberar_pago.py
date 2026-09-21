import asyncio

from app.domain.pagos.repository import IPagoRepository
from app.domain.pagos.value_objects import TrabajoId
from app.infrastructure.messaging.publicador import PublicadorPulsar
from app.common.logging_utils import configurar_logging

logger = configurar_logging("application.commands.liberar_pago")

class LiberarPago:
    def __init__(
        self,
        pago_repo: IPagoRepository,
        publicador: PublicadorPulsar,
    ) -> None:
        self._pago_repo = pago_repo
        self._publicador = publicador

    async def ejecutar(self, trabajo_id: str) -> None:
        from app.infrastructure.messaging.esquemas import PagoLiberadoMensaje
        
        pagos = await asyncio.to_thread(self._pago_repo.obtener_por_trabajo, TrabajoId.desde_str(trabajo_id))
        # Simulamos encontrar el pago y liberarlo
        if not pagos:
            logger.warning(f"No se encontró pago para trabajo {trabajo_id} al liberar")
            return
            
        pago = pagos[0] # Tomamos el primero para simular
        
        from app.infrastructure.persistence.models_db import TransaccionORM
        from app.common.db import SessionLocal
        
        with SessionLocal() as db:
            tx = TransaccionORM(
                pago_id=pago.id,
                tipo="LIBERACION",
                estado="EXITOSA"
            )
            db.add(tx)
            db.commit()
            
        # Publicar PagoLiberado
        evento_msg = PagoLiberadoMensaje(
            pago_id=str(pago.id),
            trabajo_id=trabajo_id,
            monto=float(pago.monto.valor),
            moneda=pago.monto.moneda
        )
        self._publicador.publicar_evento(evento_msg, "hda/pagos/pago.liberado", "PagoLiberado", correlation_id=trabajo_id)
