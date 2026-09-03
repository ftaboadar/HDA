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
"""

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
            if servicio.proveedor_esta_habilitado(evento.proveedor_id):
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

        elif isinstance(evento, VerificacionAgotoReintentos):
            log_evento(
                logger,
                "evento_dominio_verificacion_agoto_reintentos",
                verificacion_id=str(evento.verificacion_id),
                motivo_falla=evento.motivo_falla,
            )
            await publicador.publicar_fallida(
                {
                    "verificacion_id": str(evento.verificacion_id),
                    "proveedor_id": str(evento.proveedor_id),
                    "motivo_falla": evento.motivo_falla,
                }
            )
