import asyncio
import json
from typing import Any

from app.common.config import settings
from app.common.logging_utils import configurar_logging, log_evento
from app.application.commands.retener_pago import RetenerPago
from app.application.commands.liberar_pago import LiberarPago
from app.application.commands.compensar import CompensarPago

logger = configurar_logging("infrastructure.messaging.consumidor_comandos")

class ConsumidorComandosSaga:
    def __init__(
        self,
        retener_pago: RetenerPago,
        liberar_pago: LiberarPago,
        compensar_pago: CompensarPago,
        service_url: str = None
    ):
        self._retener_pago = retener_pago
        self._liberar_pago = liberar_pago
        self._compensar_pago = compensar_pago
        self._service_url = service_url or settings.pulsar_service_url
        self._cliente: Any = None
        self._consumidores = []
        self._corriendo = False
        
    async def iniciar(self):
        import pulsar
        self._cliente = pulsar.Client(self._service_url)
        self._corriendo = True
        
        # Suscribirse a los tópicos de los comandos
        topics = [
            "hda/pagos/pago.retener",
            "hda/pagos/pago.liberar",
            "hda/pagos/pago.compensar"
        ]
        
        for topic in topics:
            consumidor = self._cliente.subscribe(
                topic,
                subscription_name="pagos-saga-sub",
                consumer_type=pulsar.ConsumerType.Shared
            )
            self._consumidores.append(consumidor)
            asyncio.create_task(self._escuchar(consumidor))
            
        logger.info("Consumidor de comandos saga iniciado en Pagos")

    async def _escuchar(self, consumidor):
        loop = asyncio.get_event_loop()
        while self._corriendo:
            try:
                msg = await loop.run_in_executor(None, lambda: consumidor.receive(timeout_millis=1000))
                
                try:
                    data = json.loads(msg.data().decode("utf-8"))
                    props = msg.properties()
                    tipo = props.get("tipo_evento", "")
                    
                    if "retener" in msg.topic() or tipo == "RetenerPago":
                        await self._retener_pago.ejecutar(
                            trabajo_id=data.get("trabajo_id"),
                            proveedor_id=data.get("proveedor_id", "N/A"),
                            monto=data.get("monto", "0"),
                            moneda=data.get("moneda", "COP"),
                            region=data.get("region", "CO"),
                            pasarela=data.get("pasarela", "stripe")
                        )
                    elif "liberar" in msg.topic() or tipo == "LiberarPago":
                        await self._liberar_pago.ejecutar(
                            trabajo_id=data.get("trabajo_id")
                        )
                    elif "compensar" in msg.topic() or tipo == "CompensarPago":
                        await self._compensar_pago.ejecutar(
                            trabajo_id=data.get("trabajo_id")
                        )
                        
                    consumidor.acknowledge(msg)
                except Exception as ex:
                    logger.error(f"Error procesando mensaje: {ex}")
                    consumidor.negative_acknowledge(msg)
                    
            except Exception as e:
                # Timeout
                await asyncio.sleep(0.1)

    def detener(self):
        self._corriendo = False
        for c in self._consumidores:
            c.close()
        if self._cliente:
            self._cliente.close()
