from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="API de Siniestros")

class FacturaRequest(BaseModel):
    trabajo_id: str
    monto: float
    moneda: str

@app.get("/salud")
def salud():
    return {"status": "ok"}

@app.post("/v1/facturar-a-partner")
def facturar_a_partner(request: FacturaRequest):
    # Simulated internal endpoint FacturarAPartner
    from app.common.logging_utils import log_evento
    log_evento("FacturaEmitida", request.trabajo_id, "API", {"monto": request.monto, "moneda": request.moneda})
    return {"status": "facturado", "trabajo_id": request.trabajo_id}
