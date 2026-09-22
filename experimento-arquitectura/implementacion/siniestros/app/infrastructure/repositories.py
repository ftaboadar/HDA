from sqlalchemy.orm import Session
from app.domain.entities import Siniestro
from app.infrastructure.database import SiniestroModel
import json

class SiniestroRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, siniestro_id: str) -> Siniestro:
        model = self.session.query(SiniestroModel).filter(SiniestroModel.id == siniestro_id).first()
        if not model: return None
        siniestro = Siniestro(
            siniestro_id=model.id,
            cliente_id=model.cliente_id,
            monto_reclamado=model.monto_reclamado,
            estado=model.estado,
            reserva=model.reserva
        )
        siniestro.facturas = json.loads(model.facturas) if model.facturas else []
        return siniestro

    def save(self, siniestro: Siniestro):
        model = self.session.query(SiniestroModel).filter(SiniestroModel.id == siniestro.id).first()
        if not model:
            model = SiniestroModel(
                id=siniestro.id,
                cliente_id=siniestro.cliente_id,
                monto_reclamado=siniestro.monto_reclamado,
                estado=siniestro.estado,
                reserva=siniestro.reserva,
                facturas=json.dumps(siniestro.facturas)
            )
            self.session.add(model)
        else:
            model.estado = siniestro.estado
            model.reserva = siniestro.reserva
            model.facturas = json.dumps(siniestro.facturas)
        self.session.commit()
