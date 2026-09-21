from pydantic import BaseModel
from src.scoring.infraestructura.repositorios.repositorio_perfil import (
    RepositorioPerfil,
)
from src.scoring.infraestructura.mensajeria.productor import (
    publicar_scoring_actualizado,
)


class ComandoActualizarScoring(BaseModel):
    cliente_id: str
    exito: bool


class HandlerActualizarScoring:
    def __init__(self, repositorio: RepositorioPerfil):
        self.repositorio = repositorio

    def handle(self, comando: ComandoActualizarScoring):
        perfil = self.repositorio.obtener_por_cliente_id(comando.cliente_id)
        perfil.registrar_trabajo_finalizado(comando.exito)

        self.repositorio.guardar(perfil)

        # Publicar eventos de dominio generados
        for evento in perfil.eventos:
            if evento.tipo == "ScoringActualizado":
                publicar_scoring_actualizado(perfil.cliente_id, perfil.puntaje)
        perfil.eventos.clear()
