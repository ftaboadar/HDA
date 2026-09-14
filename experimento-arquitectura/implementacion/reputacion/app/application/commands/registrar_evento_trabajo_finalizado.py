"""Comando invocado por el consumidor de `trabajos.finalizado`
(infrastructure/messaging/consumidor_pulsar.py). Es evento de INTEGRACIÓN,
publicado por Gestión de Trabajos vía Pulsar -- ver plan de Entrega 4,
sección 4.

Alcance DELIBERADAMENTE mínimo: la guía del profesor (plan, sección 1.1)
es explícita en que en esta entrega "los servicios deben poder oírse... pero
no deben reaccionar ni completar la transacción todavía -- eso es parte de
la Saga, Entrega 5". Por eso este comando SOLO deja constancia de que
Reputación recibió el evento (tabla de auditoría `trabajos_vistos`, vía el
puerto `IRegistroAuditoria`) -- NO crea, actualiza ni proyecta ningún
`PerfilReputacion`, y no dispara ninguna calificación automática. Encadenar
esto con el agregado de reputación real es trabajo explícitamente fuera de
alcance hasta la Saga."""

from app.application.ports.registro_auditoria import IRegistroAuditoria


class RegistrarEventoTrabajoFinalizado:
    def __init__(self, registro: IRegistroAuditoria) -> None:
        self._registro = registro

    def ejecutar(self, trabajo_id: str, proveedor_id: str, payload: dict) -> None:
        self._registro.registrar_trabajo_finalizado(
            trabajo_id=trabajo_id, proveedor_id=proveedor_id, payload=payload
        )
