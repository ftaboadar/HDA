import time
import uuid
import pulsar
from pulsar.schema import Record, String, Long, JsonSchema


class EventoDominioRecord(Record):
    id_evento = String()
    correlation_id = String()
    causation_id = String()
    tipo_evento = String()
    timestamp = Long()
    payload = String()  # This could be a serialized JSON


class PublicadorEventos:
    def __init__(self, url="pulsar://localhost:6650"):
        self.client = pulsar.Client(url)

    def publicar(
        self,
        topic: str,
        tipo_evento: str,
        payload_dict: dict,
        correlation_id: str = None,
        causation_id: str = None,
    ):
        producer = self.client.create_producer(
            topic, schema=JsonSchema(EventoDominioRecord)
        )
        import json

        evento = EventoDominioRecord(
            id_evento=str(uuid.uuid4()),
            correlation_id=correlation_id or str(uuid.uuid4()),
            causation_id=causation_id or str(uuid.uuid4()),
            tipo_evento=tipo_evento,
            timestamp=int(time.time() * 1000),
            payload=json.dumps(payload_dict),
        )
        producer.send(evento)
        producer.close()


class ConsumidorEventos:
    def __init__(self, url="pulsar://localhost:6650"):
        self.client = pulsar.Client(url)

    def consumir(self, topic: str, subscription: str, callback):
        consumer = self.client.subscribe(
            topic,
            subscription_name=subscription,
            schema=JsonSchema(EventoDominioRecord),
        )
        try:
            while True:
                msg = consumer.receive()
                try:
                    evento = msg.value()
                    import json

                    payload = json.loads(evento.payload)
                    callback(evento, payload)
                    consumer.acknowledge(msg)
                except Exception as e:
                    consumer.negative_acknowledge(msg)
                    print(f"Error procesando mensaje: {e}")
        except KeyboardInterrupt:
            pass
        finally:
            consumer.close()
