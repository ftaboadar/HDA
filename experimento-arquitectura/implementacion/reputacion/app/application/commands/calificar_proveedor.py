"""Comando -- MUTA estado (CQS: ver
`application/queries/consultar_perfil_reputacion.py` para el lado de solo
lectura, que nunca pasa por aquí). Carga el agregado desde el Event Store
(o lo crea si es la primera calificación de ese proveedor), aplica la regla
de negocio (`PerfilReputacion.calificar`, que valida el rango 1-5) y
persiste SOLO los eventos nuevos -- nunca un estado derivado."""

from app.domain.reputacion.event_store import IEventStore
from app.domain.reputacion.perfil_reputacion import PerfilReputacion
from app.domain.reputacion.value_objects import Garantia, ProveedorId, TrabajoId


class CalificarProveedor:
    def __init__(self, event_store: IEventStore) -> None:
        self._event_store = event_store

    def ejecutar(
        self,
        proveedor_id: str,
        trabajo_id: str,
        puntaje: int,
        comentario: str | None = None,
        garantia_dias: int | None = None,
    ) -> PerfilReputacion:
        pid = ProveedorId(proveedor_id)
        eventos_previos = self._event_store.cargar_eventos(pid.valor)
        perfil = (
            PerfilReputacion.desde_eventos(eventos_previos)
            if eventos_previos
            else PerfilReputacion.crear(pid)
        )

        version_esperada = perfil.version
        perfil.calificar(
            trabajo_id=TrabajoId(trabajo_id),
            puntaje=puntaje,
            comentario=comentario,
            garantia=Garantia(garantia_dias) if garantia_dias is not None else None,
        )

        nuevos_eventos = perfil.recoger_eventos_no_confirmados()
        self._event_store.guardar_eventos(pid.valor, nuevos_eventos, version_esperada)
        return perfil
