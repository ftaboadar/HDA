from dataclasses import dataclass, field
import uuid
from typing import List, Optional
from datetime import datetime
from app.seedwork.aggregate_root import AggregateRoot
from app.seedwork.entity import Entity
from .value_objects import Franja, TipoBloqueFranja
from .events import SuscripcionCreada, CicloSuscripcionGenerado


@dataclass
class CicloSuscripcion(Entity):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    suscripcion_id: str = ""
    numero_ciclo: int = 1
    proveedor_id: Optional[str] = None
    fecha_generacion: datetime = field(default_factory=datetime.utcnow)
    completado: bool = False


@dataclass
class Suscripcion(AggregateRoot):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cliente_id: str = ""
    franja: Franja = field(
        default_factory=lambda: Franja(dia_semana=0, bloque=TipoBloqueFranja.MANANA)
    )
    proveedor_continuo_id: Optional[str] = None
    ciclos: List[CicloSuscripcion] = field(default_factory=list)

    def iniciar_suscripcion(
        self, cliente_id: str, dia_semana: int, bloque: TipoBloqueFranja
    ):
        self.cliente_id = cliente_id
        self.franja = Franja(dia_semana=dia_semana, bloque=bloque)
        self.add_event(
            SuscripcionCreada(
                suscripcion_id=self.id,
                cliente_id=self.cliente_id,
                dia_semana=self.franja.dia_semana,
                bloque=self.franja.bloque.value,
            )
        )

    def generar_siguiente_ciclo(self):
        numero = len(self.ciclos) + 1
        es_primer_ciclo = numero == 1
        # Si no es el primero, ya debería tener un proveedor si el anterior finalizó con uno, pero la asignación de
        # proveedor_continuo_id se hace cuando el primer trabajo finaliza.
        nuevo_ciclo = CicloSuscripcion(
            suscripcion_id=self.id,
            numero_ciclo=numero,
            proveedor_id=self.proveedor_continuo_id if not es_primer_ciclo else None,
        )
        self.ciclos.append(nuevo_ciclo)
        self.add_event(
            CicloSuscripcionGenerado(
                suscripcion_id=self.id,
                ciclo_id=nuevo_ciclo.id,
                proveedor_id=nuevo_ciclo.proveedor_id,
                es_primer_ciclo=es_primer_ciclo,
                dia_semana=self.franja.dia_semana,
                bloque=self.franja.bloque.value,
            )
        )

    def actualizar_proveedor_continuo(self, proveedor_id: str):
        # A13: Continuidad del proveedor. Se actualiza cuando finaliza un trabajo.
        self.proveedor_continuo_id = proveedor_id
