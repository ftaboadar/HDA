import pulsar
from pulsar.schema import Record, String, Integer, JsonSchema
import json
import time
from app.solicitudes.infrastructure.read_model import VistasSolicitudes
from app.solicitudes.infrastructure.repositorio import RepositorioSolicitudes

class TrabajoCompletadoSchema(Record):
    solicitud_id = String()
    estado = String()
    progreso = Integer()

def start_worker():
    client = pulsar.Client('pulsar://localhost:6650')
    consumer = client.subscribe(
        'persistent://public/default/trabajos-completados',
        subscription_name='marketplace-worker-sub',
        schema=JsonSchema(TrabajoCompletadoSchema)
    )
    
    vista = VistasSolicitudes()
    repositorio = RepositorioSolicitudes()

    print("Worker CQS iniciado, escuchando respuestas asíncronas...")
    while True:
        try:
            msg = consumer.receive()
            data = msg.value()
            
            # CQS: Actualizar modelo de lectura
            vista.actualizar(
                solicitud_id=data.solicitud_id,
                cliente_id="N/A", 
                detalles="N/A",
                estado=data.estado,
                progreso=data.progreso
            )
            
            # Persistencia real del lado de escritura
            repositorio.actualizar_estado(data.solicitud_id, data.estado)
            
            consumer.acknowledge(msg)
            print(f"Procesado evento de actualización: {data.solicitud_id} al {data.progreso}%")
        except Exception as e:
            print(f"Error procesando mensaje: {e}")
            time.sleep(1)

if __name__ == '__main__':
    start_worker()
