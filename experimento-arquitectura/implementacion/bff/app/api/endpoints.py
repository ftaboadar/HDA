import asyncio
import httpx
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any

router = APIRouter()

MARKETPLACE_URL = "http://marketplace:8000"
SINIESTROS_URL = "http://siniestros:8000"

async def forward_request(method: str, url: str, request: Request, payload: dict = None):
    async with httpx.AsyncClient() as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, params=request.query_params)
            elif method.upper() == "POST":
                response = await client.post(url, json=payload)
            else:
                raise HTTPException(status_code=405, detail="Method Not Allowed")
            
            if response.status_code >= 400:
                raise HTTPException(status_code=response.status_code, detail=response.text)
                
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@router.post("/solicitudes", tags=["Marketplace"])
async def gateway_crear_solicitud(request: Request, payload: Dict[str, Any]):
    url = f"{MARKETPLACE_URL}/api/v1/solicitudes"
    return await forward_request("POST", url, request, payload)

@router.post("/siniestros/aprobacion", tags=["Siniestros"])
async def gateway_aprobar_siniestro(request: Request, payload: Dict[str, Any]):
    url = f"{SINIESTROS_URL}/api/v1/siniestros/aprobacion"
    return await forward_request("POST", url, request, payload)

@router.get("/estado/{correlation_id}", tags=["Gateway - Aggregator"])
async def gateway_consultar_estado(request: Request, correlation_id: str):
    async with httpx.AsyncClient() as client:
        req_marketplace = client.get(f"{MARKETPLACE_URL}/api/v1/solicitudes/{correlation_id}")
        req_siniestros = client.get(f"{SINIESTROS_URL}/api/v1/siniestros/{correlation_id}")
        
        res_m, res_s = await asyncio.gather(req_marketplace, req_siniestros, return_exceptions=True)
        
        estado_global = {"correlation_id": correlation_id, "marketplace": None, "siniestros": None}
        
        if not isinstance(res_m, Exception) and res_m.status_code == 200:
            estado_global["marketplace"] = res_m.json()
        else:
            estado_global["marketplace"] = {"error": "Estado no disponible"}

        if not isinstance(res_s, Exception) and res_s.status_code == 200:
            estado_global["siniestros"] = res_s.json()
        else:
            estado_global["siniestros"] = {"error": "Estado no disponible"}
            
        return estado_global
