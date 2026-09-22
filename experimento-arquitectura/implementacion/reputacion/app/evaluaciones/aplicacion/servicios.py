from app.evaluaciones.domain.entidades import ReputacionPartner
from app.evaluaciones.domain.eventos import ReputacionPublicada
from app.seedwork.infraestructura.pulsar.mensajeria import Mensajeria
from pulsar.schema import JsonSchema

class ServicioReputacion:
    def __init__(self, repositorio, mensajeria: Mensajeria):
        self.repositorio = repositorio
        self.mensajeria = mensajeria

    def procesar_novedad_resuelta(self, partner_id: str, calificacion: float):
        reputacion = self.repositorio.obtener(partner_id)
        nueva_reputacion = reputacion.actualizar_promedio(calificacion)
        self.repositorio.guardar(nueva_reputacion)

        evento = ReputacionPublicada(
            partner_id=partner_id,
            nuevo_promedio=nueva_reputacion.promedio_actual
        )
        self.mensajeria.publicar("persistent://hda/evaluaciones/reputacion.publicada", evento, schema=JsonSchema(ReputacionPublicada))
        
    def procesar_trabajo_finalizado(self, partner_id: str, calificacion: float):
        self.procesar_novedad_resuelta(partner_id, calificacion)
