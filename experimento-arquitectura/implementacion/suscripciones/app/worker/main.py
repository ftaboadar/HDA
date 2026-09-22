import pulsar
from pulsar.schema import Record, String, Float, JsonSchema
from app.aplicacion.comandos import RegistrarCargoTrabajoComando, ManejadorRegistrarCargoTrabajo
from app.infraestructura.repositorio_suscripciones_sql import RepositorioSuscripcionesSQLite
import json

class TrabajoFinalizadoPayload(Record):
    id_trabajo = String()
    id_cliente = String()
    costo_final = Float()

def main():
    client = pulsar.Client('pulsar://localhost:6650')
    consumer = client.subscribe(
        'trabajos.finalizado',
        subscription_name='suscripciones-worker',
        schema=JsonSchema(TrabajoFinalizadoPayload)
    )

    repositorio = RepositorioSuscripcionesSQLite()
    manejador = ManejadorRegistrarCargoTrabajo(repositorio)

    print("Worker de Suscripciones iniciado. Esperando trabajos finalizados...")
    try:
        while True:
            msg = consumer.receive()
            try:
                data = msg.value()
                comando = RegistrarCargoTrabajoComando(
                    id_cliente=data.id_cliente,
                    id_trabajo=data.id_trabajo,
                    costo=data.costo_final
                )
                manejador.manejar(comando)
                consumer.acknowledge(msg)
            except Exception as e:
                print(f"Error procesando mensaje: {e}")
                consumer.negative_acknowledge(msg)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()

if __name__ == "__main__":
    main()
