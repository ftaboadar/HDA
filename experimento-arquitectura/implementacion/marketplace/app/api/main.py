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


@app.get("/salud")
def salud():
    """Healthcheck de Cloud Run (CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §5).
    Antes de este cambio este servicio no lo exponía — Cloud Run no tenía
    forma de verificar que el contenedor estuviera realmente sirviendo."""
    return {"status": "ok", "service": "marketplace-api"}


@app.post("/solicitudes")
def crear_solicitud(req: SolicitudRequest):
    try:
        solicitud_id = servicio_crear_solicitud.ejecutar(req.cliente_id, req.detalles)
        return {"id": solicitud_id, "estado": "CREADA"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
