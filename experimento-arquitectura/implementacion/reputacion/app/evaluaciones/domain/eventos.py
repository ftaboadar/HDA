from pulsar.schema import Record, String, Float


class ReputacionPublicada(Record):
    partner_id = String()
    nuevo_promedio = Float()
