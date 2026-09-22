"""Entrypoint del worker de Proveedores en Cloud Run (CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §5):
arranca **todos** los consumidores Pulsar del servicio en hilos y expone
`GET /salud` en :8080 — responde 200 solo si todos siguen vivos.

Hasta este cambio este archivo tenía, a mano, un único consumidor de
`trabajos.finalizado` con `pulsar.Client` directo e instanciaba
`RevalidarProveedor(None, None)` (repo/publicador nulos: revienta en cuanto
llega un mensaje real) — y **no existía ningún consumidor de
`verificacion.solicitudes`**, así que `POST /verificaciones` publicaba la
solicitud y nadie la procesaba: la verificación quedaba en PENDIENTE para
siempre (ver ESTADO-IMPLEMENTACION.md).

Los dos consumidores reales que este archivo arranca ahora:

- `app.worker.pulsar_consumer` — consume `verificacion.solicitudes` (la
  pieza que faltaba), corre `procesar_verificacion()` +
  `RegistrarIntento` por cada intento, con DLQ nativa de Pulsar
  (`pulsar_topology.construir_dead_letter_policy`).
- `app.worker.consumidor_trabajos_finalizado` — consume `trabajos.finalizado`
  (Gestión de Trabajos -> Proveedores) y lo registra vía
  `RegistrarEventoTrabajoFinalizado` (comando ya existente, ver su propio
  docstring: es un "skeleton de oír" deliberado, sin disparar revalidación
  automática — eso es la Saga de Entrega 5, aún no construida).

Decisión de diseño (ver también app/verificacion/infrastructure/messaging/consumidor_pulsar.py):
el consumidor de `trabajos.finalizado` que este archivo arrancaba antes
llamaba a `RevalidarProveedor`, un comando cuyo `ejecutar()` es un `pass`
literal (ver su propio archivo y el docstring de app/api/main.py, que explica
por qué esa pieza deliberadamente NO se expone). Existía además un segundo
consumidor de `trabajos.finalizado`, huérfano
(`app/verificacion/infrastructure/messaging/consumidor_pulsar.py`), que
importaba una clase `PulsarMensajeria` inexistente (la real se llama
`Mensajeria`, sin método `subscribe`) — nunca pudo haber corrido y no lo
importa nadie. En vez de arreglar ese duplicado para volver a invocar un
comando que es un stub, se consolida en el consumidor YA CORRECTO y ya
cableado con un comando real (`RegistrarEventoTrabajoFinalizado`):
`app.worker.consumidor_trabajos_finalizado`. `consumidor_pulsar.py` queda
documentado como huérfano/superado (no se borra, para no perder el rastro de
la decisión), no se vuelve a llamar desde ningún punto de entrada."""

from __future__ import annotations

import asyncio
import threading

from app.common.config import settings
from app.common.logging_utils import configurar_logging, log_evento
from app.seedwork.infraestructura.worker import crear_app_worker
from app.worker import consumidor_trabajos_finalizado, pulsar_consumer

logger = configurar_logging("worker.main")


class _ConsumidorEnHilo:
    """Adapta un bucle async `main()` (uno por módulo en `app/worker/`,
    cada uno dueño de su propio `pulsar.Client`/consumidor/suscripción) al
    protocolo `Consumidor` que exige `crear_app_worker` — mismo patrón que
    `gestion-de-trabajos`/`marketplace`, sin reescribir la lógica de
    consumo ya existente y probada en `pulsar_consumer.py` /
    `consumidor_trabajos_finalizado.py`."""

    def __init__(self, suscripcion: str, corutina_principal) -> None:
        self.suscripcion = suscripcion
        self._corutina_principal = corutina_principal
        self._hilo: threading.Thread | None = None

    def iniciar_en_hilo(self) -> None:
        def _ejecutar() -> None:
            try:
                asyncio.run(self._corutina_principal())
            except Exception:  # noqa: BLE001 — el hilo muere; vivo() -> False -> /salud 503
                logger.exception("consumidor_crasheo: %s", self.suscripcion)

        self._hilo = threading.Thread(target=_ejecutar, name=self.suscripcion, daemon=True)
        self._hilo.start()

    def vivo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def detener(self) -> None:
        # Los bucles internos (`while True: consumidor.receive(...)`) no
        # exponen cancelación cooperativa; al ser hilos daemon, mueren con
        # el proceso. Cloud Run reinicia la instancia completa cuando
        # `/salud` reporta 503 (ver crear_app_worker), que es la señal real
        # de recuperación en este PoC.
        pass


def _fabrica_consumidores() -> list[_ConsumidorEnHilo]:
    return [
        _ConsumidorEnHilo(settings.pulsar_suscripcion_solicitudes, pulsar_consumer.main),
        _ConsumidorEnHilo(
            settings.pulsar_suscripcion_trabajos_finalizado,
            consumidor_trabajos_finalizado.main,
        ),
    ]


def _al_iniciar() -> None:
    log_evento(
        logger,
        "worker_proveedores_arrancando",
        topico_solicitudes=settings.pulsar_topic_solicitudes,
        topico_trabajos_finalizado=settings.pulsar_topic_trabajos_finalizado,
    )


app = crear_app_worker(_fabrica_consumidores, al_iniciar=_al_iniciar)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
