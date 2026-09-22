from pulsar.schema import Record, String, Float

class TrabajoFinalizadoSchema(Record):
    trabajo_id = String()
    fotografo_id = String()
    calificacion = Float()
