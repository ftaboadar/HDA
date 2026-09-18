"""Puerto de aplicación — registro liviano de trabajos finalizados, propio
de ESTE servicio (Regla 5, criterio 4: comunicación intra-servicio por
eventos de dominio, no por llamada directa entre módulos).

`CrearTrabajo` nunca escribe aquí directamente: `Trabajo.finalizar()`
produce el evento de DOMINIO `TrabajoFinalizado`, y es
`application/dispatcher_eventos_dominio.py` quien, al reaccionar a ese
evento, puebla este registro — así el flujo interno ("un trabajo terminó, y
alguien debe poder consultarlo sin releer el agregado completo") queda
demostrado por evento de dominio, no por escritura directa desde el
comando.

Separación de Pagos (historial): antes de que Pagos fuera un microservicio
aparte, este mismo puerto (con el mismo nombre y forma) también era leído
por `PagarTrabajo` (entonces submódulo ACL de este proceso) para enterarse
de un trabajo finalizado sin acoplarse a `ITrabajoRepository`. Ahora que
Pagos es OTRO proceso, tiene su propia copia local de este puerto
(`implementacion/pagos/app/application/ports/registro_trabajos.py`) — no lo
importa de aquí. Este puerto se queda en `gestion-de-trabajos` porque
`CrearTrabajo`/el dispatcher de ESTE servicio lo siguen necesitando para su
propio registro local, independientemente de qué haga Pagos con sus datos."""

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
