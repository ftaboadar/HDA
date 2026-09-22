"""Eventos de DOMINIO del agregado Verificacion — todos internos, delgados,
nunca cruzan a un broker directamente (ver clasificación completa en
11-implementacion-ddd-verificacion.md, sección 5, y
app/application/dispatcher_eventos_dominio.py para cómo un handler de
aplicación puede reaccionar a uno de estos publicando, si corresponde, un
evento de INTEGRACIÓN distinto)."""

from dataclasses import dataclass

from app.domain.seedwork.domain_event import DomainEvent
from app.domain.verificacion.value_objects import ProveedorId, ResultadoIntento, VerificacionId


@dataclass(frozen=True)
class IntentoRegistrado(DomainEvent):
    verificacion_id: VerificacionId
    numero_intento: int
    resultado: ResultadoIntento


@dataclass(frozen=True)
class VerificacionCompletada(DomainEvent):
    verificacion_id: VerificacionId
    proveedor_id: ProveedorId


@dataclass(frozen=True)
class VerificacionAgotoReintentos(DomainEvent):
    verificacion_id: VerificacionId
    proveedor_id: ProveedorId
    motivo_falla: str
