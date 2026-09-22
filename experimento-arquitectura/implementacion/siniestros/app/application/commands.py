from dataclasses import dataclass

@dataclass
class AprobarSiniestroCommand:
    siniestro_id: str
    monto_aprobado: float

@dataclass
class ProcesarFacturaCommand:
    siniestro_id: str
    factura_id: str
    monto: float

@dataclass
class CompensarReservaCommand:
    siniestro_id: str
    monto_adicional: float
