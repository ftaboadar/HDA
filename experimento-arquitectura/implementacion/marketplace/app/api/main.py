from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.solicitudes.application.crear_solicitud import CrearSolicitud
from app.solicitudes.infrastructure.repositorio import RepositorioSolicitudes

app = FastAPI(title="Marketplace API")

class SolicitudRequest(BaseModel):
    cliente_id: str
    detalles: str

repositorio = RepositorioSolicitudes()
servicio_crear_solicitud = CrearSolicitud(repositorio)

@app.post("/solicitudes")
def crear_solicitud(req: SolicitudRequest):
    try:
        solicitud_id = servicio_crear_solicitud.ejecutar(req.cliente_id, req.detalles)
        return {"id": solicitud_id, "estado": "CREADA"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
