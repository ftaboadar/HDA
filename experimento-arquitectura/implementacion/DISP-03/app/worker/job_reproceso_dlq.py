"""Job batch de reproceso automático de la DLQ (sección 2, punto 3 y sección
2.1 del plan de Entrega 4). En vez de un cron ciego por tiempo fijo, este job
monitorea el backlog del tópico DLQ de Pulsar vía la API de estadísticas del
Admin REST (`GET /admin/v2/persistent/{tenant}/{namespace}/{topic}/stats`,
`msgBacklog`) y dispara el comando YA EXISTENTE `ReprocesarDesdeDLQ` (no se
reescribe, se reutiliza tal cual) cuando el backlog supera un umbral
configurable (`settings.pulsar_dlq_backlog_umbral`).

Cuidado importante, explícito (ver docstring de `pulsar_topology.py`): el
"backlog de Pulsar" que este job mide es el del tópico de APLICACIÓN
`settings.pulsar_topic_fallidas` (`verificacion.fallida-dlq`, donde
`publicar_fallida()` escribe cuando `procesar_verificacion()` agota sus
propios reintentos con éxito) — NO la DeadLetterPolicy NATIVA de la
suscripción de `pulsar_consumer.py` (`TOPIC_SOLICITUDES_DLQ_NATIVO`, una red
de seguridad de infraestructura para mensajes que ni siquiera llegaron a
procesarse). Son dos "DLQ" con propósitos distintos; monitorear la segunda
con la misma lógica quedaría como una extensión natural, fuera de alcance
de este PoC."""

import asyncio

from app.application.commands.reprocesar_desde_dlq import ReprocesarDesdeDLQ
from app.application.queries.listar_dlq import ListarDLQ
from app.common.config import settings
from app.common.logging_utils import configurar_logging, log_evento
from app.common.publicador import PublicadorPulsar
from app.infrastructure.persistence.verificacion_repository_sqlalchemy import (
    VerificacionRepositorySQLAlchemy,
)

logger = configurar_logging("worker.job_reproceso_dlq")


async def obtener_backlog(repo) -> int:
    pendientes = await asyncio.to_thread(ListarDLQ(repo).ejecutar)
    return len(pendientes)


async def _reprocesar_pendientes(repo, publicador: PublicadorPulsar) -> int:
    """Reprocesa TODO lo que hoy está en DLQ (query ya existente
    `ListarDLQ`), reutilizando el comando `ReprocesarDesdeDLQ` sin cambios —
    ver sección 2.2 del plan: "revisa reprocesar_desde_dlq.py, ya existe,
    reutilízalo, no lo reescribas"."""
    pendientes = await asyncio.to_thread(ListarDLQ(repo).ejecutar)
    comando = ReprocesarDesdeDLQ(repo, publicador)
    reprocesadas = 0
    for verificacion in pendientes:
        try:
            await comando.ejecutar(str(verificacion.id))
            reprocesadas += 1
        except Exception as exc:  # noqa: BLE001 — una falla individual no debe tumbar el job
            log_evento(
                logger,
                "reproceso_dlq_item_fallo",
                nivel="error",
                verificacion_id=str(verificacion.id),
                error=str(exc),
            )
    return reprocesadas


async def ciclo_monitoreo(repo, publicador) -> None:
    backlog = await obtener_backlog(repo)
    log_evento(
        logger,
        "dlq_backlog_medido",
        backlog=backlog,
        umbral=settings.pulsar_dlq_backlog_umbral,
    )
    if backlog >= settings.pulsar_dlq_backlog_umbral:
        reprocesadas = await _reprocesar_pendientes(repo, publicador)
        log_evento(
            logger,
            "dlq_reproceso_disparado_por_backlog",
            backlog=backlog,
            reprocesadas=reprocesadas,
        )


async def main() -> None:
    repo = VerificacionRepositorySQLAlchemy()
    publicador = PublicadorPulsar(
        service_url=settings.pulsar_service_url,
        topic_solicitudes=settings.pulsar_topic_solicitudes,
        topic_fallidas=settings.pulsar_topic_fallidas,
        topic_eventos=settings.pulsar_topic_eventos,
    )
    try:
        log_evento(
            logger,
            "job_reproceso_dlq_iniciado",
            umbral=settings.pulsar_dlq_backlog_umbral,
            intervalo_s=settings.pulsar_dlq_check_interval_s,
        )
        while True:
            try:
                await ciclo_monitoreo(repo, publicador)
            except Exception as exc:  # noqa: BLE001 — un ciclo fallido no debe tumbar el job
                log_evento(logger, "dlq_ciclo_monitoreo_fallo", nivel="error", error=str(exc))
            await asyncio.sleep(settings.pulsar_dlq_check_interval_s)
    finally:
        publicador.cerrar()


if __name__ == "__main__":
    asyncio.run(main())
