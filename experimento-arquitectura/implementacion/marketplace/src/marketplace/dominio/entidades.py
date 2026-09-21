import uuid
from dataclasses import dataclass, field
from typing import List

@dataclass
class Diagnostico:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    descripcion: str = ""
    severidad: str = ""

@dataclass
class Cotizacion:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    proveedor_id: uuid.UUID = field(default_factory=uuid.uuid4)
    valor: float = 0.0
    franja_disponibilidad: str = ""

@dataclass
class Marketplace:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    solicitud_id: uuid.UUID = field(default_factory=uuid.uuid4)
    diagnostico: Diagnostico = None
    cotizaciones: List[Cotizacion] = field(default_factory=list)
    proveedor_seleccionado_id: uuid.UUID = None

    def diagnosticar(self, descripcion: str, severidad: str):
        self.diagnostico = Diagnostico(descripcion=descripcion, severidad=severidad)

    def agregar_cotizacion(self, proveedor_id, valor, franja):
        self.cotizaciones.append(Cotizacion(proveedor_id=proveedor_id, valor=valor, franja_disponibilidad=franja))
    
    def seleccionar_proveedor(self, proveedor_id):
        self.proveedor_seleccionado_id = proveedor_id
