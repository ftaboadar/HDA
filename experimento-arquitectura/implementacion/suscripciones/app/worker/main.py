import threading
from fastapi import FastAPI
import uvicorn
from app.ciclo_suscripcion.infrastructure.messaging.consumidor import iniciar_consumidor

app = FastAPI()


@app.get("/salud")
def salud():
    # En un caso real se chequea la salud del thread del consumidor.
    return {"status": "ok", "servicio": "suscripciones-worker"}


def start_worker():
    thread = threading.Thread(target=iniciar_consumidor, daemon=True)
    thread.start()


if __name__ == "__main__":
    start_worker()
    uvicorn.run(app, host="0.0.0.0", port=8080)
