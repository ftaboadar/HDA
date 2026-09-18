"""Puerto de aplicación — registro liviano de lo que este microservicio
Pagos sabe sobre un `Trabajo` finalizado en Gestión de Trabajos (OTRO
microservicio, desde la separación).

Antes de la separación, `PagarTrabajo` vivía en el mismo proceso que
Gestión de Trabajos y este registro se poblaba por
`application/dispatcher_eventos_dominio.py` reaccionando al evento de
DOMINIO `TrabajoFinalizado` (comunicación intra-servicio por eventos, Regla
5 criterio 4). Ahora que Pagos es un microservicio independiente, esa
reacción automática entre procesos ya no es posible sin infraestructura de
integración adicional (cola/tópico) que está fuera del alcance de esta
tarea de separación — ver README.md de este servicio, sección "Frontera del
API": `POST /pagos` puebla este registro explícitamente en el mismo
request, a partir de los datos que el cliente HTTP ya conoce del trabajo.
El puerto y el principio de no acoplarse al repositorio ajeno (nunca se
importa el agregado `Trabajo` ni su repositorio) se conservan intactos —
solo cambió quién llama a `guardar()`."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from decimal import Decimal

from app.domain.pagos.value_objects import ProveedorId, Region, TrabajoId


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
