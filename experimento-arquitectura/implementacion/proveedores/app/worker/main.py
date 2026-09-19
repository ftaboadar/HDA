"""Consumidor pull de RabbitMQ (entorno local).

Procesa mensajes de forma concurrente (no uno a la vez) — esto es lo que
demuestra que una verificación lenta o fallida (ej. la certificadora caída)
NO bloquea el resto de la cola, que es exactamente la respuesta exigida por
DISP-03.

Ya no escribe el ORM directo (`actualizar_db` se eliminó): cada intento
individual se registra vía el comando `RegistrarIntento`, que carga el
agregado de dominio, aplica sus invariantes, y despacha los eventos que
resulten — incluida la publicación a DLQ, que ahora ocurre dentro del
dispatcher (reaccionando a `VerificacionAgotoReintentos`), no aquí."""

import asyncio
import json

import aio_pika

from app.application.commands.registrar_intento import RegistrarIntento
from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.mq import conectar, declarar_topologia
from app.common.publicador import PublicadorRabbitMQ
from app.domain.verificacion.value_objects import ResultadoIntento
from app.infrastructure.persistence.verificacion_repository_sqlalchemy import (
    VerificacionRepositorySQLAlchemy,
)
from app.worker.core import procesar_verificacion

logger = configurar_logging("worker.main")
CONCURRENCIA = 10
semaforo = asyncio.Semaphore(CONCURRENCIA)


async def _procesar_mensaje(
    mensaje: aio_pika.IncomingMessage, publicador: PublicadorRabbitMQ
) -> None:
    async with semaforo, mensaje.process(requeue=False):
        payload = json.loads(mensaje.body)
        verificacion_id = payload["verificacion_id"]
        proveedor_id = payload["proveedor_id"]
        tipo_verificador = payload["tipo_verificador"]

        resultado = await procesar_verificacion(verificacion_id, proveedor_id, tipo_verificador)

        repo = VerificacionRepositorySQLAlchemy()
        comando = RegistrarIntento(repo, publicador)
        for intento in resultado.detalle_intentos:
            await comando.ejecutar(
                verificacion_id=verificacion_id,
                resultado=ResultadoIntento.EXITOSO if intento.exito else ResultadoIntento.FALLIDO,
                duracion_ms=intento.duracion_ms,
                error=intento.error,
            )

        log_evento(
            logger,
            "verificacion_procesada",
            verificacion_id=verificacion_id,
            proveedor_id=proveedor_id,
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
