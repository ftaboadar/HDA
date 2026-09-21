import asyncio
import uuid

from app.application.ports.pasarela_de_pago import IPasarelaDePago
from app.application.ports.registro_trabajos import IRegistroTrabajosRepository
from app.common.logging_utils import configurar_logging
from app.domain.pagos.fabrica import FabricaPago
from app.domain.pagos.regla_regional import ReglaRegional
from app.domain.pagos.repository import IPagoRepository
from app.domain.pagos.value_objects import Dinero, Pasarela, Region, TrabajoId
from app.infrastructure.messaging.publicador import PublicadorPulsar

logger = configurar_logging("application.commands.retener_pago")


class RetenerPago:
    def __init__(
        self,
        pago_repo: IPagoRepository,
        registro_repo: IRegistroTrabajosRepository,
        reglas_regionales: dict[Region, ReglaRegional],
        pasarelas: dict[str, IPasarelaDePago],
        publicador: PublicadorPulsar,
    ) -> None:
        self._pago_repo = pago_repo
        self._registro_repo = registro_repo
        self._reglas_regionales = reglas_regionales
        self._pasarelas = pasarelas
        self._publicador = publicador

    async def ejecutar(self, trabajo_id: str, proveedor_id: str, monto: str, moneda: str, region: str, pasarela: str) -> None:
        
        from app.infrastructure.messaging.esquemas import PagoRetenidoMensaje, PagoRetencionFallidaMensaje

        try:
            # En la saga, al retener pago puede que el trabajo no exista todavía en el registro local,
            # pero el comando envía monto, moneda, region, pasarela
            pago = FabricaPago.crear(
                trabajo_id=TrabajoId.desde_str(trabajo_id),
                monto=Dinero(float(monto), moneda),
                region=Region(region),
                pasarela=Pasarela(pasarela),
            )

            # Strategy
            regla = self._reglas_regionales.get(pago.region)
            if not regla:
                raise ValueError(f"No hay ReglaRegional configurada para la región {region}")
            
            pasarela_impl = self._pasarelas.get(pasarela)
            if not pasarela_impl:
                raise ValueError(f"Pasarela desconocida: {pasarela}")

            regla.validar(pago)

            await asyncio.to_thread(self._pago_repo.guardar, pago)

            # Simulamos retención exitosa siempre
            # (en un sistema real se llama a la pasarela)
            pago.marcar_exitoso("ref_retencion_" + str(uuid.uuid4())[:8])
            await asyncio.to_thread(self._pago_repo.guardar, pago)
            
            from app.infrastructure.persistence.models_db import TransaccionORM
            from app.common.db import SessionLocal
            
            # Registrar transaccion de RETENCION
            with SessionLocal() as db:
                tx = TransaccionORM(
                    pago_id=pago.id,
                    tipo="RETENCION",
                    estado="EXITOSA"
                )
                db.add(tx)
                db.commit()

            evento_msg = PagoRetenidoMensaje(
                pago_id=str(pago.id),
                trabajo_id=trabajo_id,
                monto=float(monto),
                moneda=moneda,
                pasarela=pasarela,
                regla_regional=type(regla).__name__
            )
            self._publicador.publicar_evento(evento_msg, "hda/pagos/pago.retenido", "PagoRetenido", correlation_id=trabajo_id)

        except Exception as e:
            # Fallo en la retención
            logger.error(f"Error reteniendo pago: {e}")
            evento_fallo = PagoRetencionFallidaMensaje(
                pago_id="N/A",
                trabajo_id=trabajo_id,
                motivo=str(e)
            )
            self._publicador.publicar_evento(evento_fallo, "hda/pagos/pago.retencion-fallida", "PagoRetencionFallida", correlation_id=trabajo_id)
