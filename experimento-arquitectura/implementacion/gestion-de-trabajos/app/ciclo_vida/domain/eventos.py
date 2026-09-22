"""Evento de DOMINIO del agregado `Trabajo` — interno, delgado, nunca cruza
a Pulsar directamente (ver `app/domain/seedwork/domain_event.py` y
`app/infrastructure/messaging/publicador_pulsar.py` para la distinción
completa dominio/integración). Quien decide traducirlo y publicarlo como
evento de integración es `app/application/commands/crear_trabajo.py`, nunca
el propio agregado."""

from dataclasses import dataclass
from decimal import Decimal

from app.seedwork.dominio.domain_event import DomainEvent
from app.ciclo_vida.domain.value_objects import ProveedorId, Region, TrabajoId


@dataclass(frozen=True)
class TrabajoFinalizado(DomainEvent):
    """Carga de estado completa (no solo IDs) — ver 12-plan-entrega-4.md,
    sección 4.1: los consumidores inter-servicio (Proveedores, Reputación)
    necesitan datos distintos del trabajo y no deben tener que llamar de
    vuelta a Gestión de Trabajos bajo picos de carga (ESC-01). El timestamp
    ya lo aporta `DomainEvent.ocurrido_en`, heredado — no se duplica aquí."""

    trabajo_id: TrabajoId
    proveedor_id: ProveedorId
    monto: Decimal
    moneda: str
    region: Region
