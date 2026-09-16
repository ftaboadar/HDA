"""Query — solo lee, no muta estado (CQS). Reemplaza `GET /novedades/{id}`.

Agregada en esta tarea (DISP-02, ver `escenarios_calidad.md`): no existía
ningún endpoint de lectura del agregado `Novedad` antes de esta prueba de
carga — hacía falta para poder confirmar, sondeando desde fuera, cuándo el
`ThrottlerCrm` termina de drenar la cola (estado ENTREGADA/AGOTADA) sin
acoplar el caso de prueba a inspeccionar la base de datos directamente.
Mismo patrón que `ConsultarTrabajo`."""

from app.domain.novedades.novedad import Novedad
from app.domain.novedades.repository import INovedadRepository
from app.domain.novedades.value_objects import NovedadId


class ConsultarNovedad:
    def __init__(self, repo: INovedadRepository) -> None:
        self._repo = repo

    def ejecutar(self, novedad_id: str) -> Novedad | None:
        return self._repo.obtener_por_id(NovedadId.desde_str(novedad_id))
