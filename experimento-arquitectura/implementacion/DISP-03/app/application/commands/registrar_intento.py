"""Comando — reemplaza `actualizar_db()` en worker/main.py. Carga el
agregado, le pide a él mismo que registre el intento (invariantes
protegidas dentro de `Verificacion.registrar_intento`, no aquí), guarda, y
despacha los eventos de dominio acumulados.

Nota de diseño: no existe un comando público `MoverADLQ` separado (aunque
aparece en la tabla de la sección 6 del documento de propuesta) porque
exponerlo permitiría a un llamador externo forzar la transición a
FALLIDA_DLQ sin haber agotado los reintentos — precisamente el invariante 2
que el agregado protege. La transición ocurre *dentro* de este comando,
como efecto de `registrar_intento`, nunca como comando independiente."""

from app.application.dispatcher_eventos_dominio import despachar
from app.common.publicador import Publicador
from app.domain.verificacion.repository import IVerificacionRepository
from app.domain.verificacion.value_objects import ResultadoIntento, VerificacionId
from app.domain.verificacion.verificacion import Verificacion


class VerificacionNoEncontrada(Exception):
    pass


class RegistrarIntento:
    def __init__(self, repo: IVerificacionRepository, publicador: Publicador) -> None:
        self._repo = repo
        self._publicador = publicador

    async def ejecutar(
        self,
        verificacion_id: str,
        resultado: ResultadoIntento,
        duracion_ms: int,
        error: str | None = None,
    ) -> Verificacion:
        vid = VerificacionId.desde_str(verificacion_id)
        verificacion = self._repo.obtener_por_id(vid)
        if verificacion is None:
            raise VerificacionNoEncontrada(verificacion_id)

        verificacion.registrar_intento(resultado=resultado, duracion_ms=duracion_ms, error=error)
        self._repo.guardar(verificacion)

        eventos = verificacion.recoger_eventos()
        await despachar(eventos, self._repo, self._publicador)

        return verificacion
