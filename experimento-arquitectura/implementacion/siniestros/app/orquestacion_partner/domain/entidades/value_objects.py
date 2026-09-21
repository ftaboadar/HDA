from dataclasses import dataclass

@dataclass
class RedPermitida:
    homologados: list[str]

@dataclass
class MontoMaximo:
    valor: float
    moneda: str

@dataclass
class ReglaDeAprobacion:
    requiere_aprobacion_manual: bool
    umbral_monto: float
