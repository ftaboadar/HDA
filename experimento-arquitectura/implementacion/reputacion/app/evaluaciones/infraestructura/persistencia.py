from app.evaluaciones.domain.entidades import ReputacionPartner

class ReputacionRepository:
    def __init__(self):
        self.db = {} # Simulación de persistencia real

    def obtener(self, partner_id: str) -> ReputacionPartner:
        if partner_id in self.db:
            return self.db[partner_id]
        return ReputacionPartner(partner_id, 0.0, 0)

    def guardar(self, reputacion: ReputacionPartner):
        self.db[reputacion.partner_id] = reputacion
