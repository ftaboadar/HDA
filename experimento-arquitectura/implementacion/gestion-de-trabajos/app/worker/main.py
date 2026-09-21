from fastapi import FastAPI
import asyncio
import threading

app = FastAPI()

@app.get("/salud")
def salud():
    return {"status": "ok", "service": "gestion-de-trabajos-worker"}

def start_worker():
    # Aquí iría la inicialización del ConsumidorEventos
    print("Worker consumiendo eventos...")

@app.on_event("startup")
def startup_event():
    # Iniciar el worker en un hilo separado
    thread = threading.Thread(target=start_worker, daemon=True)
    thread.start()
