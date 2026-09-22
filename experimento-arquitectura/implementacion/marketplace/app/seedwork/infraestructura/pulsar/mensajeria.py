"""Mensajería Pulsar entre servicios — PLANTILLA de la Entrega 5.

Implementa CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §3 una sola vez, para que cada
servicio la copie (seedwork = copia propia por servicio, 15-…md §8 regla 4) y
no reinvente propiedades, idempotencia ni DLQ:

- `PublicadorPulsar.publicar(...)`: registra el esquema del tópico en el Schema
  Registry (`JsonSchema` de la clase `Record`, A21) y pone en las PROPIEDADES del
  mensaje `tipo_evento`, `version_esquema`, `content_type`, `productor`,
  `id_evento`, `correlation_id` y `causation_id`.
- `ConsumidorPulsar`: una suscripción Shared `<servicio>-<evento>` por tópico,
  DLQ nativa `<topico>-<suscripcion>-DLQ` tras 3 reentregas, idempotente por
  `id_evento` (`IRegistroMensajesProcesados`) y *tolerant reader*: lee el cuerpo
  como JSON plano (`msg.data()`), sin atarse a la clase `Record` del productor.

Por qué `JsonSchemaSinNulos`: el `JsonSchema` de pulsar-client escribe `null` en
todo campo opcional vacío (y un `Record` anidado sin valor sale como objeto con
todos sus campos en `null`). Ese cuerpo no valida contra
`asyncapi/hda-asyncapi.yaml`, donde un campo opcional se omite. El esquema que
se registra en el broker es el mismo; solo cambia el cuerpo, que omite los nulos.

Llamadas bloqueantes de `pulsar-client` (crear cliente, productor, send) van en
un hilo (`asyncio.to_thread`), CONVENCIONES §2. El cliente se crea de forma
perezosa: la API arranca aunque el broker no esté."""

from __future__ import annotations

import asyncio
import inspect
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from app.common.logging_utils import configurar_logging, contexto_journey, log_evento

logger = configurar_logging("infrastructure.messaging.pulsar")

CONTENT_TYPE = "application/json"
MAX_REENTREGAS = 3


# ───────────────────────────── Propiedades (CONVENCIONES §3) ─────────────────────────────


def construir_propiedades(
    *,
    tipo_evento: str,
    productor: str,
    correlation_id: str,
    causation_id: str | None = None,
    version_esquema: str = "1",
    id_evento: str | None = None,
) -> dict[str, str]:
    propiedades = {
        "tipo_evento": tipo_evento,
        "version_esquema": version_esquema,
        "content_type": CONTENT_TYPE,
        "productor": productor,
        "id_evento": id_evento or str(uuid.uuid4()),
        "correlation_id": str(correlation_id),
    }
    if causation_id:
        propiedades["causation_id"] = str(causation_id)
    return propiedades


def sin_nulos(valor: Any) -> Any:
    """Quita recursivamente las claves con `None` y los objetos que quedan
    vacíos (un `Record` anidado sin valor)."""
    if isinstance(valor, dict):
        limpio = {k: sin_nulos(v) for k, v in valor.items() if v is not None}
        return {k: v for k, v in limpio.items() if v != {}}
    if isinstance(valor, list):
        return [sin_nulos(v) for v in valor]
    return valor


def record_a_dict(mensaje: Any) -> dict:
    """Cuerpo JSON exacto que viaja por Pulsar para un `Record` (sin nulos)."""
    from pulsar.schema import JsonSchema

    crudo = json.loads(JsonSchema(type(mensaje)).encode(mensaje))
    return sin_nulos(crudo)


def _json_schema_sin_nulos(clase_record: type) -> Any:
    from pulsar.schema import JsonSchema

    class JsonSchemaSinNulos(JsonSchema):
        def encode(self, obj: Any) -> bytes:
            self._validate_object_type(obj)
            return json.dumps(record_a_dict(obj)).encode("utf-8")

    return JsonSchemaSinNulos(clase_record)


# ───────────────────────────── Publicador ─────────────────────────────


class PublicadorPulsar:
    """Un productor por tópico, creado la primera vez que se publica en él.
    Un tópico tiene una sola clase `Record` (su esquema en el registry); los
    tópicos de comandos usan una clase que une los campos de todos sus comandos
    (todos opcionales salvo los comunes de §7.1)."""

    def __init__(self, service_url: str, productor: str) -> None:
        self._service_url = service_url
        self._productor_nombre = productor
        self._cliente: Any = None
        self._productores: dict[str, tuple[type, Any]] = {}
        self._candado = threading.Lock()

    def _productor_para(self, topico: str, clase_record: type) -> Any:
        with self._candado:
            if topico in self._productores:
                clase_registrada, productor = self._productores[topico]
                if clase_registrada is not clase_record:
                    raise TypeError(
                        f"{topico} ya publica {clase_registrada.__name__}; "
                        f"un tópico tiene un solo esquema ({clase_record.__name__})"
                    )
                return productor
            import pulsar

            if self._cliente is None:
                self._cliente = pulsar.Client(self._service_url)
            productor = self._cliente.create_producer(
                topico, schema=_json_schema_sin_nulos(clase_record)
            )
            self._productores[topico] = (clase_record, productor)
            return productor

    async def publicar(
        self,
        topico: str,
        mensaje: Any,
        *,
        tipo_evento: str,
        correlation_id: str,
        causation_id: str | None = None,
        version_esquema: str = "1",
        tipo_comunicacion: str = "entre_servicios_evento",
    ) -> dict[str, str]:
        """Publica un `Record` y devuelve las propiedades enviadas (incluye
        `id_evento`, útil como `causation_id` del siguiente paso)."""
        propiedades = construir_propiedades(
            tipo_evento=tipo_evento,
            productor=self._productor_nombre,
            correlation_id=correlation_id,
            causation_id=causation_id,
            version_esquema=version_esquema,
        )
        inicio = time.perf_counter()
        productor = await asyncio.to_thread(self._productor_para, topico, type(mensaje))
        message_id = await asyncio.to_thread(
            productor.send, mensaje, properties=propiedades
        )
        log_evento(
            logger,
            "mensaje_publicado",
            canal="pulsar",
            topico=topico,
            tipo_evento=tipo_evento,
            message_id=str(message_id),
            id_evento=propiedades["id_evento"],
            causation_id=causation_id,
            correlation_id=str(correlation_id),
            version_esquema=version_esquema,
            tipo_comunicacion=tipo_comunicacion,
            duracion_publicacion_ms=round((time.perf_counter() - inicio) * 1000, 1),
        )
        return propiedades

    def cerrar(self) -> None:
        if self._cliente is not None:
            self._cliente.close()
            self._cliente = None
            self._productores.clear()


# ───────────────────────────── Consumidor ─────────────────────────────


@dataclass(frozen=True)
class MensajeRecibido:
    topico: str
    tipo_evento: str
    cuerpo: dict
    propiedades: dict[str, str]
    message_id: str

    @property
    def id_evento(self) -> str:
        # Mensajes anteriores a la Entrega 5 no traen id_evento: se usa el
        # message_id de Pulsar como clave de idempotencia (CONVENCIONES §3).
        return self.propiedades.get("id_evento") or self.message_id

    @property
    def correlation_id(self) -> str | None:
        return self.propiedades.get("correlation_id") or self.cuerpo.get("trabajo_id")

    @property
    def causation_id(self) -> str | None:
        return self.propiedades.get("causation_id")


Manejador = Callable[[MensajeRecibido], Awaitable[None] | None]


class IRegistroMensajesProcesados(Protocol):
    """Puerto de idempotencia. `reservar` devuelve False si el `id_evento` ya
    se procesó (o lo está procesando otra instancia); `liberar` deshace la
    reserva cuando el manejador falla, para que la reentrega lo reintente."""

    def reservar(self, id_evento: str, tipo_evento: str) -> bool: ...

    def liberar(self, id_evento: str) -> None: ...


class ManejadorNoRegistrado(Exception):
    pass


@dataclass
class ConsumidorPulsar:
    """Una suscripción Shared sobre un tópico. `manejadores` va por
    `tipo_evento` (un tópico de comandos trae varios). Un tipo sin manejador se
    reconoce y se descarta con log (tolerant reader: el productor pudo agregar
    un tipo nuevo antes que este consumidor)."""

    service_url: str
    topico: str
    suscripcion: str
    manejadores: dict[str, Manejador]
    registro: IRegistroMensajesProcesados
    tipo_comunicacion: str = "entre_servicios_evento"
    max_reentregas: int = MAX_REENTREGAS
    retardo_reentrega_ms: int = 1000
    _cliente: Any = field(default=None, init=False, repr=False)
    _consumidor: Any = field(default=None, init=False, repr=False)
    _hilo: threading.Thread | None = field(default=None, init=False, repr=False)
    _corriendo: threading.Event = field(
        default_factory=threading.Event, init=False, repr=False
    )
    _loop: asyncio.AbstractEventLoop | None = field(
        default=None, init=False, repr=False
    )

    @property
    def topico_dlq(self) -> str:
        return f"{self.topico}-{self.suscripcion}-DLQ"

    def conectar(self) -> None:
        import pulsar

        self._cliente = pulsar.Client(self.service_url)
        self._consumidor = self._cliente.subscribe(
            self.topico,
            subscription_name=self.suscripcion,
            consumer_type=pulsar.ConsumerType.Shared,
            initial_position=pulsar.InitialPosition.Earliest,
            negative_ack_redelivery_delay_ms=self.retardo_reentrega_ms,
            dead_letter_policy=pulsar.ConsumerDeadLetterPolicy(
                max_redeliver_count=self.max_reentregas,
                dead_letter_topic=self.topico_dlq,
            ),
        )

    def procesar(self, msg: Any) -> bool:
        """Procesa un mensaje de Pulsar; True = ack, False = nack. Separado del
        bucle para probarlo con un mensaje falso."""
        propiedades = dict(msg.properties())
        recibido = MensajeRecibido(
            topico=self.topico,
            tipo_evento=propiedades.get("tipo_evento", ""),
            cuerpo=json.loads(msg.data()),
            propiedades=propiedades,
            message_id=str(msg.message_id()),
        )
        with contexto_journey(
            correlation_id=recibido.correlation_id,
            saga_id=recibido.cuerpo.get("saga_id"),
        ):
            log_evento(
                logger,
                "mensaje_recibido",
                canal="pulsar",
                topico=self.topico,
                suscripcion=self.suscripcion,
                tipo_evento=recibido.tipo_evento,
                message_id=recibido.message_id,
                id_evento=recibido.id_evento,
                causation_id=recibido.causation_id,
                reentregas=msg.redelivery_count(),
                tipo_comunicacion=self.tipo_comunicacion,
            )
            manejador = self.manejadores.get(recibido.tipo_evento)
            if manejador is None:
                log_evento(
                    logger,
                    "mensaje_sin_manejador",
                    nivel="warning",
                    topico=self.topico,
                    tipo_evento=recibido.tipo_evento,
                    id_evento=recibido.id_evento,
                )
                return True
            if not self.registro.reservar(recibido.id_evento, recibido.tipo_evento):
                log_evento(
                    logger,
                    "mensaje_duplicado_ignorado",
                    topico=self.topico,
                    tipo_evento=recibido.tipo_evento,
                    id_evento=recibido.id_evento,
                )
                return True
            try:
                resultado = manejador(recibido)
                if inspect.isawaitable(resultado):
                    self._loop_propio().run_until_complete(resultado)
            except Exception as exc:  # noqa: BLE001 -- un mensaje malo no tumba el bucle
                self.registro.liberar(recibido.id_evento)
                log_evento(
                    logger,
                    "mensaje_fallido",
                    nivel="error",
                    topico=self.topico,
                    tipo_evento=recibido.tipo_evento,
                    id_evento=recibido.id_evento,
                    reentregas=msg.redelivery_count(),
                    va_a_dlq=msg.redelivery_count() >= self.max_reentregas,
                    error=f"{type(exc).__name__}: {exc}",
                )
                return False
            return True

    def _loop_propio(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        return self._loop

    def _bucle(self) -> None:
        while self._corriendo.is_set():
            try:
                msg = self._consumidor.receive(timeout_millis=1000)
            except Exception:  # noqa: BLE001 -- timeout de receive: se vuelve a esperar
                continue
            if self.procesar(msg):
                self._consumidor.acknowledge(msg)
            else:
                self._consumidor.negative_acknowledge(msg)

    def iniciar_en_hilo(self) -> None:
        if self._consumidor is None:
            self.conectar()
        self._corriendo.set()
        self._hilo = threading.Thread(
            target=self._bucle, name=f"consumidor-{self.suscripcion}", daemon=True
        )
        self._hilo.start()
        log_evento(
            logger,
            "consumidor_iniciado",
            topico=self.topico,
            suscripcion=self.suscripcion,
            topico_dlq=self.topico_dlq,
            tipos=sorted(self.manejadores),
        )

    def vivo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def detener(self) -> None:
        self._corriendo.clear()
        if self._hilo is not None:
            self._hilo.join(timeout=5)
        if self._cliente is not None:
            self._cliente.close()
        if self._loop is not None:
            self._loop.close()
