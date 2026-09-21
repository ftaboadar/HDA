from dataclasses import dataclass
import uuid


@dataclass
class SolicitudDiagnosticada:
    solicitud_id: uuid.UUID
    descripcion_diagnostico: str
    severidad: str


@dataclass
class ProveedorSeleccionado:
    solicitud_id: uuid.UUID
    proveedor_id: uuid.UUID
