import pulsar
import json
import time
from app.verificacion.application.commands.revalidar_proveedor import RevalidarProveedor

def main():
    client = pulsar.Client("pulsar://localhost:6650")
    
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
            except Exception:
                pass
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()

if __name__ == "__main__":
    main()
