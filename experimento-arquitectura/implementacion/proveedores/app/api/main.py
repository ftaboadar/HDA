from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Proveedores API")

class WebhookRequest(BaseModel):
    proveedor_id: str
    documento: str
    estado: str

@app.post("/webhooks/certificadora")
def recibir_webhook(req: WebhookRequest):
    # Procesar actualización asíncrona de un proveedor
    return {"status": "ok", "procesado": True}
