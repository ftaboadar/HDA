from app.seedwork.dominio.entidades import AggregateRoot, DomainEvent
from app.orquestacion_partner.domain.entidades.value_objects import RedPermitida, MontoMaximo, ReglaDeAprobacion
from dataclasses import dataclass

@dataclass
class SiniestroAprobado(DomainEvent):
    siniestro_id: str
    partner_id: str
    categoria: str
    urgencia: bool
    ubicacion: str
    region: str
    monto_maximo: float
    moneda: str

@dataclass
class DecisionPartner(DomainEvent):
    trabajo_id: str
    novedad_id: str
    partner_id: str
    decision: str
    regla_aplicada: str
    automatica: bool

class Partner(AggregateRoot):
    def __init__(self, id: str, nombre: str, regla: ReglaDeAprobacion, red: RedPermitida, monto: MontoMaximo):
        super().__init__(id)
        self.nombre = nombre
        self.regla_de_aprobacion = regla
        self.red_permitida = red
        self.monto_maximo = monto

    def registrar_siniestro(self, siniestro_id: str, categoria: str, urgencia: bool, ubicacion: str, region: str):
        evento = SiniestroAprobado(
            siniestro_id=siniestro_id,
            partner_id=self.id,
            categoria=categoria,
            urgencia=urgencia,
            ubicacion=ubicacion,
            region=region,
            monto_maximo=self.monto_maximo.valor,
            moneda=self.monto_maximo.moneda
        )
        self.add_domain_event(evento)
    
    def evaluar_novedad(self, trabajo_id: str, novedad_id: str, impacto_monto: float) -> str:
        if not self.regla_de_aprobacion.requiere_aprobacion_manual or impacto_monto <= self.regla_de_aprobacion.umbral_monto:
            self.add_domain_event(DecisionPartner(
                trabajo_id=trabajo_id,
                novedad_id=novedad_id,
                partner_id=self.id,
                decision="APROBADA",
                regla_aplicada="Umbral no superado",
                automatica=True
            ))
            return "APROBADA"
        else:
            return "PENDIENTE"
    
    def aprobar_novedad(self, trabajo_id: str, novedad_id: str, decision: str):
        self.add_domain_event(DecisionPartner(
            trabajo_id=trabajo_id,
            novedad_id=novedad_id,
            partner_id=self.id,
            decision=decision,
            regla_aplicada="Manual",
            automatica=False
        ))
