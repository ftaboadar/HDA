from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Scoring Service HDA")

@app.get("/salud")
def salud():
    return {"status": "ok", "servicio": "scoring"}
