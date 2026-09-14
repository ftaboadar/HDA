"""Puerto de salida para el registro de auditoría de eventos de INTEGRACIÓN
recibidos (ver application/commands/registrar_evento_trabajo_finalizado.py).
Deliberadamente separado de `IEventStore`: `trabajos.finalizado` no es un
hecho del agregado `PerfilReputacion` -- es solo evidencia de que este
microservicio efectivamente "oyó" un evento de otro Bounded Context (ver
plan de Entrega 4, sección 1.1). Mezclarlo con el Event Store de
PerfilReputacion inventaría una relación de negocio que todavía no existe
(esa es la Saga, Entrega 5)."""

import abc


class IRegistroAuditoria(abc.ABC):
    @abc.abstractmethod
    def registrar_trabajo_finalizado(self, trabajo_id: str, proveedor_id: str, payload: dict) -> None:
        ...
