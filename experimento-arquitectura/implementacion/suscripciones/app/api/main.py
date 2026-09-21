from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.common.db import SessionLocal, Base, engine
from pydantic import BaseModel
from app.ciclo_suscripcion.application.commands.iniciar_suscripcion import (
    IniciarSuscripcionCommand,
    ejecutar_iniciar_suscripcion,
)
from app.ciclo_suscripcion.application.queries.consultar_suscripcion import (
    ConsultarSuscripcionQuery,
    ejecutar_consultar_suscripcion,
)
from app.ciclo_suscripcion.infrastructure.persistence.repository import (
    SuscripcionRepositorySQLAlchemy,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Suscripciones API")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/salud")
def salud():
    return {"status": "ok", "servicio": "suscripciones"}


class IniciarSuscripcionReq(BaseModel):
    cliente_id: str
    dia_semana: int
    bloque: str


@app.post("/suscripciones", status_code=202)
def iniciar_suscripcion(req: IniciarSuscripcionReq, db: Session = Depends(get_db)):
    repo = SuscripcionRepositorySQLAlchemy(db)
    cmd = IniciarSuscripcionCommand(
        cliente_id=req.cliente_id, dia_semana=req.dia_semana, bloque=req.bloque
    )
    suscripcion_id = ejecutar_iniciar_suscripcion(cmd, repo)
    db.commit()
    return {"suscripcion_id": suscripcion_id}


@app.get("/suscripciones/{id}")
def consultar_suscripcion(id: str, db: Session = Depends(get_db)):
    repo = SuscripcionRepositorySQLAlchemy(db)
    query = ConsultarSuscripcionQuery(id=id)
    suscripcion = ejecutar_consultar_suscripcion(query, repo)
    if not suscripcion:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    return {
        "id": suscripcion.id,
        "cliente_id": suscripcion.cliente_id,
        "dia_semana": suscripcion.franja.dia_semana,
        "bloque": suscripcion.franja.bloque.value,
        "proveedor_continuo_id": suscripcion.proveedor_continuo_id,
        "ciclos": [
            {
                "id": c.id,
                "numero_ciclo": c.numero_ciclo,
                "proveedor_id": c.proveedor_id,
                "completado": c.completado,
            }
            for c in suscripcion.ciclos
        ],
    }
