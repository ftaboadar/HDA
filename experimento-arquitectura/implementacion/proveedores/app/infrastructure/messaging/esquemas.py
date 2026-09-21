from pulsar.schema import Record, String, Float

class PublicarElegiblesRecord(Record):
    comando_id = String()
    saga_id = String()
    correlation_id = String()
    origen = String()
    origen_id = String()

class ElegiblesCalculadosRecord(Record):
    evento_id = String()
    saga_id = String()
    correlation_id = String()
    origen = String()
    origen_id = String()
    proveedores = String() # JSON array string with [{id, score}, ...]

class ReservarFranjaRecord(Record):
    comando_id = String()
    saga_id = String()
    correlation_id = String()
    proveedor_id = String()
    tecnico_id = String()
    fecha_franja = String()
    bloque = String()

class FranjaReservadaRecord(Record):
    evento_id = String()
    saga_id = String()
    correlation_id = String()
    reserva_id = String()
    monto = Float()
    moneda = String()

class FranjaRechazadaRecord(Record):
    evento_id = String()
    saga_id = String()
    correlation_id = String()
    origen = String()
    origen_id = String()
