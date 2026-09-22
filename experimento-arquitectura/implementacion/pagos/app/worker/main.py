import asyncio

from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging
from app.domain.pagos.regla_regional import ReglaRegional
from app.domain.pagos.value_objects import Region
from app.infrastructure.adapters.pasarela_mercadopago import PasarelaMercadoPago
from app.infrastructure.adapters.pasarela_stripe import PasarelaStripe
from app.infrastructure.adapters.regla_brasil import ReglaBrasil
from app.infrastructure.adapters.regla_colombia import ReglaColombia
from app.infrastructure.persistence.pago_repository_sqlalchemy import (
    PagoRepositorySQLAlchemy,
)
from app.infrastructure.persistence.registro_trabajos_repository_sqlalchemy import (
    RegistroTrabajosRepositorySQLAlchemy,
)

# Importar el consumidor (que crearemos / moveremos)
from app.worker.consumidor_pulsar import ConsumidorComandosSaga
from app.seedwork.infraestructura.pulsar.mensajeria import PublicadorPulsar

# Comandos
from app.application.commands.retener_pago import RetenerPago
from app.application.commands.liberar_pago import LiberarPago
from app.application.commands.compensar import CompensarPago

# Outbox job
from app.worker.outbox_publisher import OutboxPublisher

logger = configurar_logging("worker.main")


async def main():
    logger.info("Iniciando Worker de Pagos...")
    Base.metadata.create_all(bind=engine)

    pago_repo = PagoRepositorySQLAlchemy()
    registro_repo = RegistroTrabajosRepositorySQLAlchemy()

    reglas_regionales: dict[Region, ReglaRegional] = {
        Region.COLOMBIA: ReglaColombia(),
        Region.BRASIL: ReglaBrasil(),
    }
    pasarelas = {
        "stripe": PasarelaStripe(),
        "mercadopago": PasarelaMercadoPago(),
    }

    publicador = PublicadorPulsar()

    retener_pago = RetenerPago(
        pago_repo, registro_repo, reglas_regionales, pasarelas, publicador
    )
    liberar_pago = LiberarPago(pago_repo, publicador)
    compensar_pago = CompensarPago(pago_repo, publicador)

    consumidor = ConsumidorComandosSaga(
        retener_pago=retener_pago,
        liberar_pago=liberar_pago,
        compensar_pago=compensar_pago,
    )

    outbox_publisher = OutboxPublisher(publicador)

    try:
        # Iniciar consumidor en background
        asyncio.create_task(consumidor.iniciar())

        # Iniciar outbox loop
        await outbox_publisher.iniciar()
    except asyncio.CancelledError:
        logger.info("Worker cancelado")
    except Exception as e:
        logger.error(f"Error en worker: {e}")
    finally:
        consumidor.detener()


if __name__ == "__main__":
    asyncio.run(main())
