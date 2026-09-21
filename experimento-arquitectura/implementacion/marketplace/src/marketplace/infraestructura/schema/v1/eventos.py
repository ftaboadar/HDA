from pulsar.schema import Record, String


class SolicitudDiagnosticadaPayload(Record):
    solicitud_id = String()
    descripcion_diagnostico = String()
    severidad = String()


class ProveedorSeleccionadoPayload(Record):
    solicitud_id = String()
    proveedor_id = String()


class ElegiblesPublicadosPayload(Record):
    solicitud_id = String()
    proveedores = String()  # JSON list
