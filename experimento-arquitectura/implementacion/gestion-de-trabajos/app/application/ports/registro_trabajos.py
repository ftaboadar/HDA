"""Puerto de aplicación — registro liviano de lo que el módulo ACL de Pagos
sabe sobre un `Trabajo` finalizado en el módulo Trabajo, DENTRO del mismo
servicio (Regla 5, criterio 4: comunicación intra-servicio por eventos de
dominio, no por llamada directa entre módulos).

Antes de este puerto, `PagarTrabajo` recibía `ITrabajoRepository` (el
repositorio del OTRO módulo) inyectado directamente y lo usaba para leer
`region`/`monto` del trabajo — acoplando Pagos al repositorio ajeno en vez
de a un evento. Con este puerto, Pagos deja de depender de
`ITrabajoRepository` por completo: aprende de un trabajo finalizado
únicamente a través del evento de dominio `TrabajoFinalizado`, despachado
por `application/dispatcher_eventos_dominio.py`, que puebla este registro.

Mismo principio que `app/application/ports/eventos_recibidos.py` en DISP-03
(registro liviano de eventos recibidos de OTRO microservicio) — aquí es
intra-servicio, no inter-servicio, pero la misma idea de "no acoplarse al
repositorio ajeno, solo al evento" aplica igual entre módulos del mismo
servicio."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from decimal import Decimal

from app.domain.trabajo.value_objects import ProveedorId, Region, TrabajoId


@dataclass(frozen=True)
class RegistroTrabajoElegible:
    trabajo_id: TrabajoId
    proveedor_id: ProveedorId
    monto: Decimal
    moneda: str
    region: Region


class IRegistroTrabajosRepository(abc.ABC):
    @abc.abstractmethod
    def guardar(self, registro: RegistroTrabajoElegible) -> None: ...

    @abc.abstractmethod
    def obtener_por_trabajo(
        self, trabajo_id: TrabajoId
    ) -> RegistroTrabajoElegible | None: ...
