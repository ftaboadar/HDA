from pulsar.schema import Record, String, Integer

class ReputacionPublicadaMensaje(Record):
    proveedor_id = String()
    puntaje = Integer()

class ScoringActualizadoMensaje(Record):
    proveedor_id = String()
    scoring = Integer()
