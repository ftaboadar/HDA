import pulsar
from pulsar.schema import JsonSchema
from marketplace.infraestructura.schema.v1.eventos import ElegiblesPublicadosPayload


def consumir_elegibles(broker_url: str):
    client = pulsar.Client(broker_url)
    consumer = client.subscribe(
        "persistent://public/default/elegibles-publicados",
        subscription_name="marketplace-sub",
        schema=JsonSchema(ElegiblesPublicadosPayload),
    )

    while True:
        msg = consumer.receive()
        try:
            print(f"Recibido: {msg.value()}")
            consumer.acknowledge(msg)
        except Exception:
            consumer.negative_acknowledge(msg)
