import pulsar
import json
import time
import threading
from fastapi import FastAPI
import uvicorn
from app.verificacion.application.commands.revalidar_proveedor import RevalidarProveedor
from app.common.config import settings

app = FastAPI()

@app.get("/salud")
def salud():
    return {"status": "ok", "service": "proveedores-worker"}

def start_worker():
    client = pulsar.Client(settings.pulsar_service_url)
    
    # DLQ manual o tópico de reintentos se configuraría aquí idealmente.
    consumer = client.subscribe(
        'persistent://hda/gestion-trabajos/trabajos.finalizado',
        subscription_name='proveedores-trabajos.finalizado'
    )

    comando_revalidar = RevalidarProveedor(None, None)

    print("Worker de Proveedores escuchando trabajos finalizados para revalidación...")
    try:
        while True:
            try:
                msg = consumer.receive(timeout_millis=100)
                data = json.loads(msg.data().decode('utf-8'))
                
                proveedor_id = data.get('partner_id') or data.get('proveedor_id')
                if proveedor_id:
                    comando_revalidar.ejecutar(proveedor_id)
                
                consumer.acknowledge(msg)
            except Exception as e:
                print(f"Error procesando mensaje: {e}")
                pass
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()

@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=start_worker, daemon=True)
    thread.start()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
