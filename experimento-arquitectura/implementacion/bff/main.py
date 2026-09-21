import os
import uuid
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Hogar de los Alpes - BFF",
    description="Backend For Frontend para orquestar y enrutar peticiones a microservicios core.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs from environment (or default values)
GESTION_TRABAJOS_URL = os.getenv("GESTION_TRABAJOS_URL", "http://gestion-de-trabajos:8000")
PROVEEDORES_URL = os.getenv("PROVEEDORES_URL", "http://proveedores:8000")
PAGOS_URL = os.getenv("PAGOS_URL", "http://pagos:8000")
SAGAS_URL = os.getenv("SAGAS_URL", "http://sagas:8000")

# HTTPX Client with strict timeout
TIMEOUT = httpx.Timeout(10.0, connect=5.0)

async def proxy_request(request: Request, base_url: str, path: str):
    correlation_id = request.headers.get("X-Correlation-Id")
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    headers = dict(request.headers)
    headers.pop("host", None)
    headers["X-Correlation-Id"] = correlation_id
    
    # Read body if any
    body = await request.body()
    
    target_url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    query_params = request.scope.get("query_string", b"").decode("utf-8")
    if query_params:
        target_url = f"{target_url}?{query_params}"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=headers
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={k: v for k, v in response.headers.items() if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")}
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Error connecting to downstream service: {exc}")

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    request.scope["headers"].append((b"x-correlation-id", correlation_id.encode()))
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    return response

# Rutas agrupadas por actor/contexto

# DUEÑOS (Gestion de trabajos)
@app.api_route("/v1/dueños/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_duenos(path: str, request: Request):
    return await proxy_request(request, GESTION_TRABAJOS_URL, path)

# PROVEEDORES
@app.api_route("/v1/proveedores/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_proveedores(path: str, request: Request):
    return await proxy_request(request, PROVEEDORES_URL, path)

# PAGOS
@app.api_route("/v1/pagos/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_pagos(path: str, request: Request):
    return await proxy_request(request, PAGOS_URL, path)

# SAGAS (Orquestador)
@app.api_route("/v1/sagas/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_sagas(path: str, request: Request):
    return await proxy_request(request, SAGAS_URL, path)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "bff"}
