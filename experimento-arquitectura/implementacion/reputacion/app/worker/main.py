import pulsar
import json
import time
from app.evaluaciones.aplicacion.servicios import ServicioReputacion
from app.evaluaciones.infraestructura.persistencia import ReputacionRepository
from app.seedwork.infraestructura.pulsar.mensajeria import Mensajeria

def main():
    client = pulsar.Client("pulsar://localhost:6650")
    
    repositorio = ReputacionRepository()
    mensajeria = Mensajeria()
    servicio = ServicioReputacion(repositorio, mensajeria)

    consumer_trabajos = client.subscribe(
        'persistent://hda/gestion-trabajos/trabajos.finalizado',
        subscription_name='reputacion-trabajos.finalizado'
    )
    
    consumer_novedad = client.subscribe(
        'persistent://hda/gestion-trabajos/novedad.resuelta',
        subscription_name='reputacion-novedad.resuelta'
    )

    print("Worker de Reputación escuchando eventos...")
    try:
        while True:
            try:
                msg = consumer_trabajos.receive(timeout_millis=100)
                data = json.loads(msg.data().decode('utf-8'))
                servicio.procesar_trabajo_finalizado(data.get('partner_id'), data.get('calificacion', 5.0))
                consumer_trabajos.acknowledge(msg)
            except Exception:
                pass
            
            try:
                msg = consumer_novedad.receive(timeout_millis=100)
                data = json.loads(msg.data().decode('utf-8'))
                servicio.procesar_novedad_resuelta(data.get('partner_id'), data.get('calificacion', 5.0))
                consumer_novedad.acknowledge(msg)
            except Exception:
                pass
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()

if __name__ == "__main__":
    main()
