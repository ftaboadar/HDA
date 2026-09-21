import uuid
import pulsar
from app.common.config import settings


class PublicadorPulsar:
    def __init__(self, url=None):
        self.url = url or settings.pulsar_service_url
        self.client = pulsar.Client(self.url)

    def publicar_evento(self, record_obj, topic, tipo_evento, correlation_id=""):
        producer = self.client.create_producer(
            topic, schema=pulsar.schema.JsonSchema(type(record_obj))
        )
        properties = {
            "tipo_evento": tipo_evento,
            "version_esquema": "1",
            "content_type": "application/json",
            "productor": "reputacion",
            "id_evento": str(uuid.uuid4()),
            "correlation_id": correlation_id,
        }
        producer.send(record_obj, properties=properties)
        producer.close()
