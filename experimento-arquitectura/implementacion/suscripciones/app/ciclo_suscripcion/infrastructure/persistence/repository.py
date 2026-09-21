from typing import Optional
from sqlalchemy.orm import Session
from app.ciclo_suscripcion.domain.repositories import SuscripcionRepository
from app.ciclo_suscripcion.domain.entities import Suscripcion, CicloSuscripcion
from app.ciclo_suscripcion.domain.value_objects import Franja, TipoBloqueFranja
from .models import SuscripcionModel, CicloSuscripcionModel

class SuscripcionRepositorySQLAlchemy(SuscripcionRepository):
    def __init__(self, session: Session):
        self.session = session

    def get(self, id: str) -> Optional[Suscripcion]:
        model = self.session.query(SuscripcionModel).filter_by(id=id).first()
        if not model:
            return None
        
        s = Suscripcion(
            id=model.id,
            cliente_id=model.cliente_id,
            proveedor_continuo_id=model.proveedor_continuo_id,
            franja=Franja(dia_semana=model.dia_semana, bloque=TipoBloqueFranja(model.bloque))
        )
        s.ciclos = [
            CicloSuscripcion(
                id=c.id,
                suscripcion_id=c.suscripcion_id,
                numero_ciclo=c.numero_ciclo,
                proveedor_id=c.proveedor_id,
                fecha_generacion=c.fecha_generacion,
                completado=c.completado
            ) for c in model.ciclos
        ]
        return s

    def save(self, suscripcion: Suscripcion):
        model = self.session.query(SuscripcionModel).filter_by(id=suscripcion.id).first()
        if not model:
            model = SuscripcionModel(id=suscripcion.id)
            self.session.add(model)
        
        model.cliente_id = suscripcion.cliente_id
        model.dia_semana = suscripcion.franja.dia_semana
        model.bloque = suscripcion.franja.bloque.value
        model.proveedor_continuo_id = suscripcion.proveedor_continuo_id

        # Sincronizar ciclos
        existentes = {c.id: c for c in model.ciclos}
        for ciclo in suscripcion.ciclos:
            if ciclo.id in existentes:
                c_model = existentes[ciclo.id]
                c_model.proveedor_id = ciclo.proveedor_id
                c_model.completado = ciclo.completado
            else:
                c_model = CicloSuscripcionModel(
                    id=ciclo.id,
                    suscripcion_id=suscripcion.id,
                    numero_ciclo=ciclo.numero_ciclo,
                    proveedor_id=ciclo.proveedor_id,
                    fecha_generacion=ciclo.fecha_generacion,
                    completado=ciclo.completado
                )
                model.ciclos.append(c_model)
        self.session.flush()
