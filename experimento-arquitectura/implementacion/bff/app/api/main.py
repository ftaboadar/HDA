"""BFF — único punto de entrada REST para actores externos (A25). No tiene
dominio propio: solo enruta síncrono hacia la API de cada servicio (§8/§9 de
15-arquitectura-entrega-5.md) y propaga `X-Correlation-Id`. Por eso no sigue
el layout hexagonal domain/application/infrastructure de los demás
servicios — no hay lógica de negocio que aislar de infraestructura, solo un
proxy HTTP.

Consolidación: existían dos implementaciones divergentes (`bff/main.py` +
`bff/app/main.py` con `bff/app/api/endpoints.py`), ninguna en el path que
usan Terraform/Dockerfile (`app.api.main:app`, ver infra/service.tf). Esta
es la única que queda; se basó en la variante de `bff/main.py` (proxy
genérico configurable por variable de entorno, rutas `/v1/...` que
coinciden con el ejemplo `GET /v1/sagas/{id}` de la sección 7.1 del
documento de arquitectura) en vez de la variante de `app/main.py` (rutas
`/api/v1/...` hardcodeadas a solo 2 de los 9 servicios), y se completó con
el resto de servicios del journey.

Limitación conocida (fuera de alcance de este cambio): `infra/service.tf`
del BFF no declara `env_vars` con las URLs de Cloud Run de los servicios
downstream, así que en GCP este proxy cae a los defaults de
docker-compose (`http://<servicio>:8000`), que no resuelven fuera de una
red Docker local. Falta agregar esas variables al stack de Terraform del
BFF para que el proxy funcione contra el despliegue real."""

import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Hogar de los Alpes - BFF",
    description="Backend For Frontend: único punto de entrada REST que enruta síncrono a las APIs de cada microservicio.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URLs de los servicios downstream — configurables por variable de entorno
# (ver docker-compose.yml para los defaults locales; en Cloud Run deben
# venir de env_vars de infra/service.tf, ver nota de módulo más arriba).
SERVICE_URLS = {
    "dueños": os.getenv("GESTION_TRABAJOS_URL", "http://gestion-de-trabajos:8000"),
    "proveedores": os.getenv("PROVEEDORES_URL", "http://proveedores:8000"),
    "pagos": os.getenv("PAGOS_URL", "http://pagos:8000"),
    "sagas": os.getenv("SAGAS_URL", os.getenv("GESTION_TRABAJOS_URL", "http://gestion-de-trabajos:8000")),
    "siniestros": os.getenv("SINIESTROS_URL", "http://siniestros:8080"),
    "marketplace": os.getenv("MARKETPLACE_URL", "http://marketplace:8080"),
    "suscripciones": os.getenv("SUSCRIPCIONES_URL", "http://suscripciones:8080"),
    "scoring": os.getenv("SCORING_URL", "http://scoring:8080"),
    "reputacion": os.getenv("REPUTACION_URL", "http://reputacion:8000"),
}

TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def proxy_request(request: Request, base_url: str, path: str) -> Response:
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())

    headers = dict(request.headers)
    headers.pop("host", None)
    headers["X-Correlation-Id"] = correlation_id

    body = await request.body()

    target_url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    query_params = request.scope.get("query_string", b"").decode("utf-8")
    if query_params:
        target_url = f"{target_url}?{query_params}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.request(
                method=request.method, url=target_url, content=body, headers=headers
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
                },
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502, detail=f"Error connecting to downstream service: {exc}"
            )


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    request.scope["headers"].append((b"x-correlation-id", correlation_id.encode()))
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    return response


def _registrar_ruta(prefijo: str, service_key: str) -> None:
    base_url = SERVICE_URLS[service_key]

    async def _route(path: str, request: Request) -> Response:
        return await proxy_request(request, base_url, path)

    app.add_api_route(
        f"/v1/{prefijo}/{{path:path}}",
        _route,
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        name=f"route_{service_key}",
    )


for _prefijo, _service_key in [
    ("dueños", "dueños"),
    ("proveedores", "proveedores"),
    ("pagos", "pagos"),
    ("sagas", "sagas"),
    ("siniestros", "siniestros"),
    ("marketplace", "marketplace"),
    ("suscripciones", "suscripciones"),
    ("scoring", "scoring"),
    ("reputacion", "reputacion"),
]:
    _registrar_ruta(_prefijo, _service_key)


@app.get("/salud")
def salud():
    return {"status": "ok", "servicio": "bff"}


@app.get("/health")
def health_check():
    # Alias histórico de /salud (algunos journeys/postman ya lo usan);
    # /salud es el obligatorio por convención (CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §5).
    return salud()
