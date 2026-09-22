from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from app.infrastructure.database import SessionLocal, Base, engine
from app.infrastructure.repositories import SiniestroRepository
from app.application.handlers import CommandHandler, QueryHandler, MessagePublisher
from app.application.commands import AprobarSiniestroCommand
from app.application.queries import GetSiniestroQuery
from app.domain.entities import Siniestro

app = FastAPI(title="Siniestros API")


@app.on_event("startup")
def startup() -> None:
    # Se crea el esquema al arrancar (no al importar el módulo), para que
    # uvicorn pueda bindear el puerto y /salud responda aunque la conexión a
    # la base de datos tarde en estar lista (mismo patrón que
    # gestion-de-trabajos/app/api/main.py).
    Base.metadata.create_all(bind=engine)


@app.get("/salud")
def salud():
    return {"status": "ok"}

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def get_publisher():
    publisher = MessagePublisher()
    try: yield publisher
    finally: publisher.close()

class AprobarRequest(BaseModel):
    monto_aprobado: float

@app.post("/siniestros/{siniestro_id}/aprobar")
def aprobar_siniestro(siniestro_id: str, req: AprobarRequest, db = Depends(get_db), publisher = Depends(get_publisher)):
    repo = SiniestroRepository(db)
    handler = CommandHandler(repo, publisher)
    cmd = AprobarSiniestroCommand(siniestro_id=siniestro_id, monto_aprobado=req.monto_aprobado)
    try:
        handler.handle_aprobar_siniestro(cmd)
        return {"msg": "Siniestro aprobado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/siniestros/{siniestro_id}")
def get_siniestro(siniestro_id: str, db = Depends(get_db)):
    repo = SiniestroRepository(db)
    handler = QueryHandler(repo)
    query = GetSiniestroQuery(siniestro_id=siniestro_id)
    result = handler.handle_get_siniestro(query)
    if not result:
        raise HTTPException(status_code=404, detail="Siniestro no encontrado")
    return result

@app.post("/siniestros/mock/{siniestro_id}")
def create_mock(siniestro_id: str, db = Depends(get_db)):
    repo = SiniestroRepository(db)
    siniestro = Siniestro(siniestro_id=siniestro_id, cliente_id="C123", monto_reclamado=1000.0)
    repo.save(siniestro)
    return {"msg": "Siniestro mock creado"}
