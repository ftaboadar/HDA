"""Contrato de serialización HTTP (Pydantic) — distinto del vocabulario de
dominio en `domain/*/`. `api/main.py` es el único lugar que traduce entre
ambos; ni `application/` ni `domain/` conocen estas clases."""

from pydantic import BaseModel, Field


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
