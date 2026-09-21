import pulsar
from pulsar.schema import JsonSchema, Record, String, Integer
import json

class ScoringActualizadoEvento(Record):
    cliente_id = String()
    nuevo_puntaje = Integer()

def publicar_scoring_actualizado(cliente_id: str, nuevo_puntaje: int):
    client = pulsar.Client('pulsar://localhost:6650')
    producer = client.create_producer(
        'persistent://public/default/scoring-actualizado',
        schema=JsonSchema(ScoringActualizadoEvento)
    )
    
    evento = ScoringActualizadoEvento(cliente_id=cliente_id, nuevo_puntaje=nuevo_puntaje)
    # Using json.dumps and JsonSchema
    producer.send(evento)
    client.close()
