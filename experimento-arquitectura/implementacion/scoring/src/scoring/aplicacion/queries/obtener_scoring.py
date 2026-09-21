from src.scoring.infraestructura.repositorios.repositorio_perfil import RepositorioPerfil

class QueryObtenerScoring:
    def __init__(self, cliente_id: str):
        self.cliente_id = cliente_id

class HandlerObtenerScoring:
    def __init__(self, repositorio: RepositorioPerfil):
        self.repositorio = repositorio

    def handle(self, query: QueryObtenerScoring):
        perfil = self.repositorio.obtener_por_cliente_id(query.cliente_id)
        return {
            "cliente_id": perfil.cliente_id,
            "puntaje": perfil.puntaje,
            "historial_trabajos": perfil.historial_trabajos
        }
