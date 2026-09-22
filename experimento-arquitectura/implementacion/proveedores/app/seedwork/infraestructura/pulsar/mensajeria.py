import pulsar


class Mensajeria:
    def __init__(self, service_url="pulsar://localhost:6650"):
        self.client = pulsar.Client(service_url)

    def publicar(self, topico: str, mensaje: dict, schema=None):
        if schema:
            producer = self.client.create_producer(topico, schema=schema)
            producer.send(mensaje)
        else:
            producer = self.client.create_producer(topico)
            producer.send(mensaje)
        producer.close()

    def cerrar(self):
        self.client.close()
