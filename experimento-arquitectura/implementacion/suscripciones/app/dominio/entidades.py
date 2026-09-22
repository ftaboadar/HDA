from dataclasses import dataclass, field
from datetime import datetime
import uuid
from app.dominio.eventos import EventoDominio, CargoRegistrado

@dataclass
class Cargo:
    id_cargo: str
    id_trabajo: str
    monto: float
    fecha: datetime

@dataclass
class Suscripcion:
    id_suscripcion: str
    id_cliente: str
    saldo: float = 0.0
    cargos: list[Cargo] = field(default_factory=list)
    eventos: list[EventoDominio] = field(default_factory=list)

    def registrar_cargo_por_trabajo(self, id_trabajo: str, monto: float):
        id_cargo = str(uuid.uuid4())
        nuevo_cargo = Cargo(
            id_cargo=id_cargo,
            id_trabajo=id_trabajo,
            monto=monto,
            fecha=datetime.now()
        )
        self.cargos.append(nuevo_cargo)
        self.saldo += monto
        
        self.eventos.append(
            CargoRegistrado(
                id_suscripcion=self.id_suscripcion,
                id_cargo=id_cargo,
                id_trabajo=id_trabajo,
                monto=monto,
                fecha=nuevo_cargo.fecha
            )
        )
