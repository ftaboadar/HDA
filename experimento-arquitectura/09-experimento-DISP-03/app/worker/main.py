"""Consumidor pull de RabbitMQ (entorno local).

Procesa mensajes de forma concurrente (no uno a la vez) — esto es lo que
demuestra que una verificación lenta o fallida (ej. la certificadora caída)
NO bloquea el resto de la cola, que es exactamente la respuesta exigida por
DISP-03."""
import asyncio
import json
import uuid
from datetime import datetime

import aio_pika

from app.common.db import Base, SessionLocal, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.models_db import VerificacionORM
from app.common.mq import conectar, declarar_topologia
from app.common.publicador import PublicadorRabbitMQ
from app.worker.core import procesar_verificacion

logger = configurar_logging("worker.main")
CONCURRENCIA = 10
semaforo = asyncio.Semaphore(CONCURRENCIA)


def actualizar_db(
    verificacion_id: str, exito: bool, intentos: int, motivo: str | None
) -> None:
    with SessionLocal() as sesion:
        fila = sesion.get(VerificacionORM, uuid.UUID(verificacion_id))
        if fila is None:
            return
        fila.intentos = intentos
        if exito:
            fila.estado = "COMPLETADA"
            fila.completado_en = datetime.utcnow()
        else:
            fila.estado = "FALLIDA_DLQ"
            fila.motivo_falla = motivo
            fila.en_dlq_desde = datetime.utcnow()
        sesion.commit()


async def _procesar_mensaje(
    mensaje: aio_pika.IncomingMessage, publicador: PublicadorRabbitMQ
) -> None:
    async with semaforo:
        async with mensaje.process(requeue=False):
            payload = json.loads(mensaje.body)
            verificacion_id = payload["verificacion_id"]
            proveedor_id = payload["proveedor_id"]
            tipo_verificador = payload["tipo_verificador"]

            resultado = await procesar_verificacion(
                verificacion_id, proveedor_id, tipo_verificador
            )
            await asyncio.get_event_loop().run_in_executor(
                None,
                actualizar_db,
                verificacion_id,
                resultado.exito,
                resultado.intentos,
                resultado.motivo_falla,
            )
            if not resultado.exito:
                await publicador.publicar_fallida(
                    {
                        **payload,
                        "motivo_falla": resultado.motivo_falla,
                        "intentos": resultado.intentos,
                        "fallido_en": datetime.utcnow().isoformat(),
                    }
                )
            log_evento(
                logger,
                "verificacion_procesada",
                verificacion_id=verificacion_id,
                exito=resultado.exito,
                intentos=resultado.intentos,
            )


async def main() -> None:
    Base.metadata.create_all(bind=engine)
    conexion = await conectar()
    canal = await conexion.channel()
    await canal.set_qos(prefetch_count=CONCURRENCIA * 2)
    exchange_sol, exchange_dlx, cola_sol, _ = await declarar_topologia(canal)
    publicador = PublicadorRabbitMQ(exchange_sol, exchange_dlx)

    log_evento(logger, "worker_iniciado", concurrencia=CONCURRENCIA)

    async with cola_sol.iterator() as it:
        tareas: set[asyncio.Task] = set()
        async for mensaje in it:
            tarea = asyncio.create_task(_procesar_mensaje(mensaje, publicador))
            tareas.add(tarea)
            tarea.add_done_callback(tareas.discard)


if __name__ == "__main__":
    asyncio.run(main())
