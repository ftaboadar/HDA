from fastapi import FastAPI
from pydantic import BaseModel
from src.scoring.aplicacion.queries.obtener_scoring import QueryObtenerScoring, HandlerObtenerScoring
from src.scoring.infraestructura.repositorios.repositorio_perfil import RepositorioPerfil

app = FastAPI(title="Scoring Service HDA")
repositorio = RepositorioPerfil()

@app.get("/salud")
def salud():
    return {"status": "ok", "servicio": "scoring"}

@app.get("/scoring/{cliente_id}")
def obtener_scoring(cliente_id: str):
    query = QueryObtenerScoring(cliente_id=cliente_id)
    handler = HandlerObtenerScoring(repositorio)
    resultado = handler.handle(query)
    return resultado
