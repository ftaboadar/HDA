"""Fábrica de infraestructura: resuelve qué adaptador concreto de
`IVerificacionExternaPort` corresponde a un `tipo_verificador`. Vive en
infrastructure/, no en el dominio — el dominio/aplicación solo conocen el
puerto, nunca esta decisión de cableado."""

from app.application.ports.verificacion_externa import IVerificacionExternaPort
from app.domain.verificacion.value_objects import TipoVerificador
from app.infrastructure.external.adaptador_certificadora import AdaptadorCertificadora
from app.infrastructure.external.adaptador_policia import AdaptadorPolicia
from app.infrastructure.external.adaptador_rues import AdaptadorRUES

_ADAPTADORES: dict[TipoVerificador, type[IVerificacionExternaPort]] = {
    TipoVerificador.POLICIA: AdaptadorPolicia,
    TipoVerificador.RUES: AdaptadorRUES,
    TipoVerificador.CERTIFICADORA: AdaptadorCertificadora,
}


def resolver_adaptador_externo(tipo_verificador: str) -> IVerificacionExternaPort:
    clase = _ADAPTADORES[TipoVerificador(tipo_verificador)]
    return clase()
