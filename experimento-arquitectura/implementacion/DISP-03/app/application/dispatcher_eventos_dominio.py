"""Despachador EN MEMORIA de eventos de dominio — el mecanismo concreto que
demuestra el criterio 4 de la Regla 5 ("comunicación intra-servicio por
eventos de dominio"). Se invoca después de que un comando guarda el
agregado; nunca antes.

Reacciones:
- `IntentoRegistrado`: solo trazabilidad (log estructurado) — no dispara
  nada más.
- `VerificacionCompletada`: consulta `ServicioDeElegibilidad`; si el
  proveedor queda habilitado, publica el evento de INTEGRACIÓN
  `ProveedorHabilitado` (cruza el Bounded Context, ver
  11-implementacion-ddd-verificacion.md sección 5) — este es el paso
  explícito que en el código anterior era una llamada de función directa
  dentro de worker/main.py.
- `VerificacionAgotoReintentos`: publica el evento de INTEGRACIÓN de DLQ ya
  existente (`publicar_fallida`, sin cambios en ese transporte).

Manejo de errores de publicación (deliberado, no un descuido): cuando este
módulo se invoca, `verificacion.registrar_intento()` y `repo.guardar()` ya
corrieron con éxito — el estado del agregado ya quedó persistido de forma
correcta. Todo lo que pasa aquí abajo es notificación de un hecho que ya es
verdad, no una escritura que deba ser atómica con ella. Por eso cada llamada
al puerto `Publicador` se envuelve en try/except: si falla (ej. el adaptador
GCP levanta `RuntimeError` porque `PUBSUB_TOPIC_SOLICITUDES` no está
configurado — ver app/common/publicador.py), se registra en nivel "error" y
NO se re-lanza. Re-lanzar rompería la garantía explícita de
worker/push_handler.py ("siempre respondemos 200 ... porque
procesar_verificacion() ya agotó sus propios reintentos internamente") y
provocaría que Pub/Sub reintregue un mensaje cuya verificación ya está en un
estado terminal (COMPLETADA o FALLIDA_DLQ) en la base de datos — el segundo
intento chocaría entonces contra el invariante de
`Verificacion.registrar_intento` (ver
tests/unit/dominio/test_verificacion_aggregate.py), una segunda falla
distinta y evitable."""

import asyncio

from app.common.logging_utils import configurar_logging, log_evento
from app.common.publicador import Publicador
from app.domain.seedwork.domain_event import DomainEvent
from app.domain.verificacion.eventos import (
    IntentoRegistrado,
    VerificacionAgotoReintentos,
    VerificacionCompletada,
)
from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.servicio_elegibilidad import ServicioDeElegibilidad

logger = configurar_logging("application.dispatcher_eventos_dominio")

ROUTING_KEY_PROVEEDOR_HABILITADO = "proveedor.habilitado"


async def despachar(
    eventos: list[DomainEvent],
    repo: IVerificacionRepository,
    publicador: Publicador,
) -> None:
    for evento in eventos:
        if isinstance(evento, IntentoRegistrado):
            log_evento(
                logger,
                "evento_dominio_intento_registrado",
                verificacion_id=str(evento.verificacion_id),
                numero_intento=evento.numero_intento,
                resultado=evento.resultado.value,
            )

        elif isinstance(evento, VerificacionCompletada):
            log_evento(
                logger,
                "evento_dominio_verificacion_completada",
                verificacion_id=str(evento.verificacion_id),
            )
            servicio = ServicioDeElegibilidad(repo)
            habilitado = await asyncio.to_thread(
                servicio.proveedor_esta_habilitado, evento.proveedor_id
            )
            if habilitado:
                try:
                    await publicador.publicar_evento(
                        ROUTING_KEY_PROVEEDOR_HABILITADO,
                        {
                            "proveedor_id": str(evento.proveedor_id),
                            "evento": "ProveedorHabilitado",
                        },
                    )
                    log_evento(
                        logger,
                        "evento_integracion_proveedor_habilitado_publicado",
                        proveedor_id=str(evento.proveedor_id),
                    )
                except Exception as exc:  # noqa: BLE001 — ver docstring del módulo
                    log_evento(
                        logger,
                        "evento_integracion_proveedor_habilitado_fallo_publicacion",
                        nivel="error",
                        proveedor_id=str(evento.proveedor_id),
                        error=str(exc),
                    )

        elif isinstance(evento, VerificacionAgotoReintentos):
            log_evento(
                logger,
                "evento_dominio_verificacion_agoto_reintentos",
                verificacion_id=str(evento.verificacion_id),
                motivo_falla=evento.motivo_falla,
            )
            try:
                await publicador.publicar_fallida(
                    {
                        "verificacion_id": str(evento.verificacion_id),
                        "proveedor_id": str(evento.proveedor_id),
                        "motivo_falla": evento.motivo_falla,
                    }
                )
            except Exception as exc:  # noqa: BLE001 — ver docstring del módulo
                log_evento(
                    logger,
                    "evento_integracion_dlq_fallo_publicacion",
                    nivel="error",
                    verificacion_id=str(evento.verificacion_id),
                    error=str(exc),
                )
