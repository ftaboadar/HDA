import pulsar
from pulsar.schema import JsonSchema, Record, String, Boolean
import json
from src.scoring.aplicacion.comandos.actualizar_scoring import (
    ComandoActualizarScoring,
    HandlerActualizarScoring,
)
from src.scoring.infraestructura.repositorios.repositorio_perfil import (
    RepositorioPerfil,
)


class TrabajoFinalizadoEvento(Record):
    cliente_id = String()
    trabajo_id = String()
    exito = Boolean()


def iniciar_consumidor():
    client = pulsar.Client("pulsar://localhost:6650")
    consumer = client.subscribe(
        "persistent://public/default/trabajo-finalizado",
        subscription_name="scoring-sub",
        schema=JsonSchema(TrabajoFinalizadoEvento),
        consumer_type=pulsar.ConsumerType.Shared,
    )

    repo = RepositorioPerfil()
    handler = HandlerActualizarScoring(repo)

    while True:
        msg = consumer.receive()
        try:
            data = msg.value()
            payload_str = json.dumps(
                {
                    "cliente_id": data.cliente_id,
                    "trabajo_id": data.trabajo_id,
                    "exito": data.exito,
                }
            )
            print(f"Evento TrabajoFinalizado recibido: {payload_str}")
            comando = ComandoActualizarScoring(
                cliente_id=data.cliente_id, exito=data.exito
            )
            handler.handle(comando)
            consumer.acknowledge(msg)
        except Exception:
            consumer.negative_acknowledge(msg)
