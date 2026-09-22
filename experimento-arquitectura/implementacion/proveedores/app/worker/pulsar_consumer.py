"""Consumidor PULL de Apache Pulsar (sección 2.2, punto 5 del plan de
Entrega 4) — reemplaza a `worker/main.py` (RabbitMQ) cuando
`settings.transporte == "pulsar"`. A diferencia de Pub/Sub (que forzó el
diseño push de `worker/push_handler.py`), Pulsar sí soporta consumo pull
nativo, así que este archivo es más parecido a `worker/main.py` que a
`push_handler.py` — mismo patrón de semáforo/concurrencia acotada, mismo
comando `RegistrarIntento` para persistir cada intento (nunca se escribe el
ORM directo aquí).

Ack vs. nack — dos niveles de "fallido" deliberadamente distintos:
- Si `procesar_verificacion()` corre de punta a punta (éxito o fracaso
  definitivo tras agotar sus propios reintentos internos), el mensaje se
  ACKea siempre — igual que `push_handler.py` siempre responde 200: la
  aplicación ya resolvió el mensaje por su cuenta y lo dejó trazado
  (`RegistrarIntento` ya movió el agregado a COMPLETADA o FALLIDA_DLQ, ver
  `app/common/publicador.py` para el tópico de aplicación
  `verificacion.fallida-dlq`).
- Si algo revienta ANTES de que eso termine (payload malformado, la BD
  caída, una excepción no controlada), se NACKea — ahí sí entra en juego la
  DeadLetterPolicy NATIVA de Pulsar (`pulsar_topology.construir_dead_letter_policy`),
  que tras `max_redeliver_count` reintentos de entrega mueve el mensaje al
  tópico técnico `TOPIC_SOLICITUDES_DLQ_NATIVO` — una red de seguridad de
  infraestructura, distinta de la DLQ de aplicación."""

import asyncio
import json

import pulsar

from app.common.config import settings
from app.common.db import Base, engine
from app.common.logging_utils import configurar_logging, log_evento
from app.common.publicador import PublicadorPulsar
from app.common.pulsar_topology import construir_dead_letter_policy
from app.verificacion.application.commands.registrar_intento import RegistrarIntento
from app.verificacion.application.procesar_verificacion import procesar_verificacion
from app.verificacion.application.queries.consultar_verificacion import ConsultarVerificacion
from app.verificacion.domain.value_objects import EstadoVerificacion, ResultadoIntento
from app.verificacion.infrastructure.persistence.verificacion_repository_sqlalchemy import (
    VerificacionRepositorySQLAlchemy,
)

logger = configurar_logging("worker.pulsar_consumer")
CONCURRENCIA = 10
semaforo = asyncio.Semaphore(CONCURRENCIA)


async def _procesar_mensaje(mensaje, consumidor, publicador: PublicadorPulsar) -> None:
    loop = asyncio.get_event_loop()
    async with semaforo:
        try:
            payload = json.loads(mensaje.data())
            verificacion_id = payload["verificacion_id"]
            proveedor_id = payload["proveedor_id"]
            tipo_verificador = payload["tipo_verificador"]

            repo = VerificacionRepositorySQLAlchemy()

            existente = await asyncio.to_thread(
                ConsultarVerificacion(repo).ejecutar, verificacion_id
            )
            if existente is not None and existente.estado in (
                EstadoVerificacion.COMPLETADA,
                EstadoVerificacion.FALLIDA_DLQ,
            ):
                log_evento(
                    logger,
                    "verificacion_redelivery_ignorada",
                    verificacion_id=verificacion_id,
                    estado=existente.estado.value,
                )
                await loop.run_in_executor(None, lambda: consumidor.acknowledge(mensaje))
                return

            resultado = await procesar_verificacion(verificacion_id, proveedor_id, tipo_verificador)
            comando = RegistrarIntento(repo, publicador)
            for intento in resultado.detalle_intentos:
                await comando.ejecutar(
                    verificacion_id=verificacion_id,
                    resultado=(
                        ResultadoIntento.EXITOSO if intento.exito else ResultadoIntento.FALLIDO
                    ),
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
            await loop.run_in_executor(None, lambda: consumidor.acknowledge(mensaje))
        except Exception as exc:  # noqa: BLE001 — ver docstring del módulo (nack -> DLQ nativa)
            log_evento(
                logger,
                "verificacion_mensaje_pulsar_fallo_no_procesado",
                nivel="error",
                error=str(exc),
            )
            await loop.run_in_executor(None, lambda: consumidor.negative_acknowledge(mensaje))


async def main() -> None:
    Base.metadata.create_all(bind=engine)

    publicador = PublicadorPulsar(
        service_url=settings.pulsar_service_url,
        topic_solicitudes=settings.pulsar_topic_solicitudes,
        topic_fallidas=settings.pulsar_topic_fallidas,
        topic_eventos=settings.pulsar_topic_eventos,
    )
    # El productor interno de PublicadorPulsar ya abrió un pulsar.Client;
    # reutilizamos un cliente propio para el consumidor en vez de exponer el
    # privado del publicador, para no acoplar el ciclo de vida de ambos.
    cliente = pulsar.Client(settings.pulsar_service_url)
    dlq_policy = construir_dead_letter_policy(max_redeliver_count=settings.max_reintentos)
    consumidor = cliente.subscribe(
        settings.pulsar_topic_solicitudes,
        subscription_name=settings.pulsar_suscripcion_solicitudes,
        consumer_type=pulsar.ConsumerType.Shared,
        dead_letter_policy=dlq_policy,
    )

    log_evento(logger, "worker_pulsar_iniciado", concurrencia=CONCURRENCIA)

    loop = asyncio.get_event_loop()
    tareas: set[asyncio.Task] = set()
    try:
        while True:
            mensaje = await loop.run_in_executor(None, consumidor.receive)
            tarea = asyncio.create_task(_procesar_mensaje(mensaje, consumidor, publicador))
            tareas.add(tarea)
            tarea.add_done_callback(tareas.discard)
    finally:
        consumidor.close()
        cliente.close()
        publicador.cerrar()


if __name__ == "__main__":
    asyncio.run(main())
