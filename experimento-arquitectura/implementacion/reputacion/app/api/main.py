"""API de Reputación (plan de Entrega 4, secciones 1.3 y 6).

CQS explícito y visible en la propia ruta: `POST /calificaciones` pasa por
el COMANDO `CalificarProveedor` (muta estado); `GET /reputacion/{id}` pasa
por la QUERY `ConsultarPerfilReputacion` (solo lee) -- nunca el mismo
objeto de aplicación para ambos casos. La API no toca `SessionLocal` ni el
ORM directo (Regla 5, criterio 2)."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.application.commands.calificar_proveedor import CalificarProveedor
from app.application.queries.consultar_perfil_reputacion import ConsultarPerfilReputacion
from app.common.db import Base, engine
from app.domain.reputacion.perfil_reputacion import PerfilReputacion, PuntajeFueraDeRango
from app.infrastructure.persistence.event_store_sqlalchemy import EventStoreSQLAlchemy

app = FastAPI(title="Reputación — API (Entrega 4 PoC, Event Sourcing)")

_event_store = EventStoreSQLAlchemy()


class CalificacionCreate(BaseModel):
    proveedor_id: str
    trabajo_id: str
    puntaje: int = Field(ge=1, le=5)
    comentario: str | None = None
    garantia_dias: int | None = None


class CalificacionOut(BaseModel):
    trabajo_id: str
    puntaje: int
    comentario: str | None
    garantia_dias: int | None


class PerfilReputacionOut(BaseModel):
    proveedor_id: str
    promedio: float
    total_calificaciones: int
    calificaciones: list[CalificacionOut]


def _a_schema(perfil: PerfilReputacion) -> PerfilReputacionOut:
    """Único punto de traducción dominio -> contrato HTTP (misma
    convención que `DISP-03/app/api/main.py::_a_schema`): el dominio no
    conoce Pydantic."""
    return PerfilReputacionOut(
        proveedor_id=str(perfil.proveedor_id),
        promedio=perfil.promedio,
        total_calificaciones=len(perfil.calificaciones),
        calificaciones=[
            CalificacionOut(
                trabajo_id=str(c.trabajo_id),
                puntaje=c.puntaje,
                comentario=c.comentario,
                garantia_dias=c.garantia.plazo_dias if c.garantia else None,
            )
            for c in perfil.calificaciones
        ],
    )


@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/salud")
async def salud():
    return {"estado": "ok"}


@app.post("/calificaciones", response_model=PerfilReputacionOut, status_code=201)
async def calificar(payload: CalificacionCreate):
    comando = CalificarProveedor(_event_store)
    try:
        perfil = comando.ejecutar(
            proveedor_id=payload.proveedor_id,
            trabajo_id=payload.trabajo_id,
            puntaje=payload.puntaje,
            comentario=payload.comentario,
            garantia_dias=payload.garantia_dias,
        )
    except PuntajeFueraDeRango as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _a_schema(perfil)


@app.get("/reputacion/{proveedor_id}", response_model=PerfilReputacionOut)
async def obtener_reputacion(proveedor_id: str):
    query = ConsultarPerfilReputacion(_event_store)
    perfil = query.ejecutar(proveedor_id)
    if perfil is None:
        raise HTTPException(status_code=404, detail="proveedor sin calificaciones registradas")
    return _a_schema(perfil)
