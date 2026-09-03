# 11. Implementación DDD del servicio de Verificación (Regla 5, 45pt)

> **Nota de rutas** (corregidas tras la reorganización de `experimento-arquitectura/` en
> `contexto/` vs. `implementacion/<experimento>/` — ver `10-estructura-multiagente.md`): este
> documento vive en `experimento-arquitectura/contexto/`, junto a `escenarios_calidad.md`,
> `REGLAS-DURAS-rubrica-entrega-3.md`, `03-contextos-acotados-TO-BE.cml` y
> `07-vista-informacion.puml` (referenciados abajo por nombre simple, como siblings). El código del
> experimento vive en `experimento-arquitectura/implementacion/DISP-03/` — todas las rutas `app/...`
> de este documento (`app/domain/`, `app/api/main.py`, `app/common/models_db.py`, etc.) son
> relativas a esa carpeta, no a este archivo.

Complementa a `../implementacion/DISP-03/plan.md` (que resuelve el experimento de **resiliencia**) y
a `escenarios_calidad.md` (DISP-03). Este documento resuelve específicamente la Regla 5 de
`REGLAS-DURAS-rubrica-entrega-3.md`: la capa de **dominio (DDD) + hexagonal + eventos internos + CQS**
que hoy no existe en `../implementacion/DISP-03/app/`. Ver también
`.claude/agents/implementador-ddd.md` (raíz del repo) para el rol que debe ejecutar esto.

**Regla de oro de este documento:** no se reemplaza nada del código de integración/resiliencia que ya
pasa 7/7 pruebas — se construye la capa de dominio **alrededor** de él (`app/domain/` y
`app/application/` son carpetas nuevas; `app/api/`, `app/worker/`, `app/common/` se refactorizan para
llamar a la nueva capa, no se reescriben).

**Decisión de modelo — ya resuelta:** este plan usa el modelo de información (B) descrito en
`CAMBIOS-PENDIENTES-ENTREGA-3.md` #0 — `Técnico`, `ProveedorPersonaNatural`/`ProveedorEmpresa`,
`Verificación`, `NivelVerificación`, `DocumentoIdentidad`. `07-vista-informacion.puml` ya fue
actualizado para reflejarlo — no hay ambigüedad pendiente entre diagrama y código.

---

## 1. Alcance

Bounded Context: **`ContextoProveedores`** (`03-contextos-acotados-TO-BE.cml`, línea ~1:
*"Dueño único del registro y verificación. Publica eventos de habilitación."*). Un solo agregado
raíz para esta pieza: `Verificacion` — mapea 1:1 con la tabla `verificaciones` que ya existe en
`app/common/models_db.py`. No se modela `Proveedor` como agregado completo en este PoC (vive
conceptualmente en el mismo contexto, pero su tabla/agregado no es necesaria para demostrar los 5
criterios de la Regla 5 ni para el experimento DISP-03) — queda anotado como extensión futura, no
como deuda de esta entrega.

---

## 2. Modelo de dominio

### Agregado — `Verificacion` (raíz)

| Campo | Tipo | Nota |
|---|---|---|
| `id` | `VerificacionId` (VO, wrapper de UUID) | |
| `proveedor_id` | `ProveedorId` (VO, wrapper de str) | referencia por ID a otro contexto, sin FK física |
| `tipo_verificador` | `TipoVerificador` (VO, enum: `POLICIA`, `RUES`, `CERTIFICADORA`) | |
| `estado` | `EstadoVerificacion` (VO, enum: `PENDIENTE`, `EN_PROCESO`, `COMPLETADA`, `FALLIDA_DLQ`) | transiciones validadas dentro del agregado, no desde fuera |
| `intentos` | `List[IntentoVerificacion]` | entidad hija, ver abajo |
| `nivel_verificacion` | `NivelVerificacion` (VO, enum: `Basica`, `Completa`) — **si se confirma modelo (B)** | qué nivel de habilitación otorga este tipo de check al aprobarse |

**Invariante 1:** una transición a `COMPLETADA` solo es válida si el último `IntentoVerificacion`
tiene `resultado = EXITOSO`.
**Invariante 2:** una transición a `FALLIDA_DLQ` solo es válida si `len(intentos) >= max_intentos` y
el último intento fue fallido — nunca se salta directo de `PENDIENTE` a `FALLIDA_DLQ`.

### Entidad hija — `IntentoVerificacion`

| Campo | Tipo |
|---|---|
| `id` | UUID |
| `numero` | int (1, 2, 3...) |
| `resultado` | `ResultadoIntento` (VO, enum: `EXITOSO`, `FALLIDO`) |
| `error` | `Optional[str]` |
| `duracion_ms` | int |
| `ocurrido_en` | datetime |

Esto **reemplaza** los campos planos `intentos: int` / `motivo_falla: str` de `VerificacionORM` por
una lista real de intentos — mejora directa de trazabilidad, que es justo lo que exige la Medida de
la respuesta de DISP-03 ("100% de verificaciones fallidas trazables"). Ver cambio #13 del manifiesto
para la migración de tabla necesaria (`intentos_verificacion`, FK a `verificaciones.id`).

### Value Objects

`VerificacionId`, `ProveedorId`, `TipoVerificador`, `EstadoVerificacion`, `ResultadoIntento`,
`NivelVerificacion` — todos inmutables, con `__eq__` por valor (no por identidad), validación en el
constructor (ej. `TipoVerificador` solo acepta los 3 valores válidos, igual que el `Literal` que ya
existe en `schemas.py` — el VO es la versión de dominio de esa misma restricción, no una duplicada
sin relación).

### Servicio de dominio — `ServicioDeElegibilidad`

Dado un `proveedor_id`, consulta (vía `IVerificacionRepository.listar_por_proveedor`) todas sus
`Verificacion` y determina si están todas `COMPLETADA`. Vive como servicio de dominio porque la
decisión de habilitación cruza múltiples instancias del agregado — no pertenece a una sola
`Verificacion`.

```python
class ServicioDeElegibilidad:
    def __init__(self, repo: IVerificacionRepository):
        self._repo = repo

    def proveedor_esta_habilitado(self, proveedor_id: ProveedorId) -> bool:
        verificaciones = self._repo.listar_por_proveedor(proveedor_id)
        if not verificaciones:
            return False
        return all(v.estado == EstadoVerificacion.COMPLETADA for v in verificaciones)
```

**Nota de alcance (a propósito, no un olvido):** el enunciado describe habilitación granular por
servicio y zona ("cada proveedor queda habilitado únicamente para lo que demostró" — paso 4 del
flujo de Verificación de proveedores). La versión de arriba simplifica eso a un booleano
"¿todas sus verificaciones están completadas?" — suficiente para demostrar los 5 criterios de la
Regla 5 sin construir el motor de reglas de habilitación por servicio/zona completo, que es negocio
adicional, no patrón DDD adicional. Si el equipo quiere cerrar esa brecha, `NivelVerificacion` ya
tiene el value object para hacerlo (extender `proveedor_esta_habilitado` a
`nivel_habilitado_para(proveedor_id, servicio, zona) -> NivelVerificacion`), pero no es necesario
para cumplir la rúbrica de esta entrega.

### Fábrica — `FabricaVerificacion`

```python
class FabricaVerificacion:
    @staticmethod
    def crear(proveedor_id: ProveedorId, tipo_verificador: TipoVerificador) -> Verificacion:
        return Verificacion(
            id=VerificacionId.nueva(),
            proveedor_id=proveedor_id,
            tipo_verificador=tipo_verificador,
            estado=EstadoVerificacion.PENDIENTE,
            intentos=[],
        )
```

### Repositorio (puerto) — `IVerificacionRepository`

```python
class IVerificacionRepository(abc.ABC):
    @abc.abstractmethod
    def guardar(self, verificacion: Verificacion) -> None: ...
    @abc.abstractmethod
    def obtener_por_id(self, id: VerificacionId) -> Optional[Verificacion]: ...
    @abc.abstractmethod
    def listar_por_proveedor(self, proveedor_id: ProveedorId) -> List[Verificacion]: ...
    @abc.abstractmethod
    def listar_en_dlq(self) -> List[Verificacion]: ...
```

### Seedwork (`app/domain/seedwork/`, sin dependencias de framework)

```
entity.py           # clase base Entity: id + __eq__ por identidad
aggregate_root.py    # extiende Entity; acumula eventos_dominio: list[DomainEvent] pendientes
value_object.py       # clase base ValueObject: __eq__ por valor, frozen dataclass
domain_event.py       # clase base DomainEvent: event_id, ocurrido_en, tipo
repository.py         # Protocol/ABC genérico IRepository[T]
```

---

## 3. Arquitectura hexagonal

```
app/
├── domain/                    ← sin imports de infraestructura, sin SQLAlchemy, sin FastAPI
│   ├── seedwork/
│   └── verificacion/
│       ├── verificacion.py          # Verificacion (AggregateRoot), IntentoVerificacion (Entity)
│       ├── value_objects.py
│       ├── eventos.py               # eventos de DOMINIO internos (ver sección 5)
│       ├── servicio_elegibilidad.py
│       ├── fabrica.py
│       └── repository.py            # IVerificacionRepository (puerto)
│
├── application/                ← orquesta dominio, CQS explícito (ver sección 6)
│   ├── commands/
│   │   ├── iniciar_verificacion.py
│   │   ├── registrar_intento.py
│   │   ├── mover_a_dlq.py
│   │   └── reprocesar_desde_dlq.py
│   ├── queries/
│   │   ├── consultar_verificacion.py
│   │   ├── listar_verificaciones.py
│   │   └── listar_dlq.py
│   └── dispatcher_eventos_dominio.py   # despachador EN MEMORIA de eventos internos (sección 5)
│
└── infrastructure/              ← todo lo que ya existe, ligeramente refactorizado
    ├── persistence/
    │   └── verificacion_repository_sqlalchemy.py  # implementa IVerificacionRepository sobre VerificacionORM (ya existe)
    ├── api/            (antes app/api/)      ← llama a application/commands y application/queries
    ├── worker/         (antes app/worker/)    ← llama a application/commands
    └── mensajeria/     (antes app/common/publicador.py, mq.py)
```

**Regla de dependencia:** `domain/` no importa nada de `application/` ni `infrastructure/`.
`application/` importa `domain/` pero no `infrastructure/` directamente — recibe las implementaciones
de los puertos por inyección (constructor), no por import directo. Esto es lo que hoy **no** existe:
`app/api/main.py` importa `VerificacionORM` y `SessionLocal` directamente en el handler de la ruta —
eso es justo la violación de hexagonal que esta refactorización corrige.

### Puerto adicional — `IVerificacionExternaPort` (cierra el segundo hueco de hexagonal)

`app/worker/core.py` hoy llama `httpx` **directo** a Policía/RUES/Certificadora — no hay puerto de
por medio, es la otra violación de hexagonal que faltaba cerrar (la primera, el acceso a BD desde
las rutas, ya está cubierta en la sección 4). Se agrega:

```python
# app/application/ports/verificacion_externa.py
class IVerificacionExternaPort(abc.ABC):
    @abc.abstractmethod
    async def verificar(self, proveedor_id: str) -> ResultadoVerificacionExterna: ...
```

Con **3 adaptadores concretos**, uno por sistema externo — no uno solo parametrizado como el mock,
porque en producción cada uno hablará un protocolo distinto (hoy los 3 mocks comparten forma HTTP
por simplicidad del PoC, pero el puerto de dominio no debe asumir eso):

```python
# app/infrastructure/external/adaptador_policia.py
class AdaptadorPolicia(IVerificacionExternaPort):
    async def verificar(self, proveedor_id: str) -> ResultadoVerificacionExterna:
        # misma llamada httpx que hoy vive en worker/core.py::_llamar_externo,
        # movida aquí detrás del puerto
        ...

# app/infrastructure/external/adaptador_rues.py
class AdaptadorRUES(IVerificacionExternaPort): ...

# app/infrastructure/external/adaptador_certificadora.py
class AdaptadorCertificadora(IVerificacionExternaPort): ...
```

`worker/core.py` deja de tener la función `_url_externa()` con el `dict` de mapeo — en su lugar,
recibe el `IVerificacionExternaPort` correcto ya resuelto por inyección (un factory simple que
elige el adaptador según `tipo_verificador`, vive en `infrastructure/config.py`, no en el dominio).
La lógica de reintentos con `tenacity` **no se toca** — sigue envolviendo la llamada, solo que ahora
la llamada es `await puerto.verificar(proveedor_id)` en vez de `await _llamar_externo(...)`.

---

## 4. Qué se toca vs. qué se preserva en el código existente

| Archivo existente | Se preserva | Se refactoriza |
|---|---|---|
| `app/common/models_db.py` | La tabla `verificaciones` en sí | Se agrega `IntentosVerificacionORM` (tabla nueva, hija) |
| `app/common/publicador.py` | Interfaz `Publicador`, adaptadores RabbitMQ/PubSub | Se agrega tercer adaptador `PublicadorKafka` |
| `app/worker/core.py` | La lógica de reintentos/backoff (`tenacity`) en sí, agnóstica de transporte | La llamada `httpx` directa a `_url_externa()` se envuelve detrás de `IVerificacionExternaPort` (ver sección 3) — hoy no hay puerto ahí, es una violación real de hexagonal que este cambio cierra |
| `app/api/main.py` | Las rutas (mismos endpoints, mismo contrato HTTP) | Los *bodies* de los handlers dejan de tocar `SessionLocal`/`VerificacionORM` directo — llaman a `application/commands/*` y `application/queries/*` |
| `app/worker/main.py` | La lógica de concurrencia (semáforo, `asyncio`) | `actualizar_db()` deja de escribir el ORM directo — llama al comando `RegistrarIntento` |
| `app/common/schemas.py` | Los `Literal`/Pydantic schemas de la API (contrato HTTP no cambia) | Nada — el dominio tiene sus propios VOs, distintos de los schemas de transporte, a propósito (no mezclar capa de dominio con capa de serialización HTTP) |

---

## 5. Regla 4 — Clasificación explícita de eventos (dominio vs. integración vs. gordo/delgado)

Esto es lo que `implementador-ddd.md` marca como **decisión pendiente, no resuelta todavía en
ningún documento** — se resuelve aquí:

| Evento | Tipo | ¿Cruza el Bounded Context? | Gordo o delgado | Transporte |
|---|---|---|---|---|
| `IntentoRegistrado` | **Dominio (interno)** | No — solo dentro de `Verificacion` | Delgado (solo `verificacion_id`, `numero_intento`, `resultado`) | En memoria, vía `dispatcher_eventos_dominio.py` — **nunca sale a Kafka/RabbitMQ** |
| `VerificacionCompletada` | **Dominio (interno)** | No | Delgado | En memoria — dispara `ServicioDeElegibilidad` para evaluar si el proveedor completo queda habilitado |
| `VerificacionAgotoReintentos` | **Dominio (interno)** | No | Delgado | En memoria — dispara el comando `MoverADLQ` |
| `VerificacionSolicitada` | **Integración** | Sí — ya existe hoy vía `publicar_solicitud` | Delgado (solo IDs + tipo) | RabbitMQ / Pub-Sub / Kafka (puerto `Publicador`) |
| `VerificacionFallidaDLQ` | **Integración** | Sí — ya existe hoy vía `publicar_fallida` | Gordo (incluye `motivo_falla`, `intentos`, contexto completo) — se decidió gordo a propósito para que quien consuma la DLQ no tenga que hacer una consulta adicional a este servicio | RabbitMQ / Pub-Sub / Kafka |
| `ProveedorHabilitado` | **Integración (nuevo)** | Sí — hacia `ContextoMarketplace`, `ContextoSiniestros`, `ContextoSuscripciones` (ver `03-contextos-acotados-TO-BE.cml`) | Gordo (incluye `proveedor_id`, `nivel_habilitacion`, `zonas_cobertura`, `timestamp`) — evita que Marketplace tenga que preguntar de vuelta | Mismo tópico de integración, nuevo routing key `proveedor.habilitado` |

**Por qué la distinción importa para la Regla 5, no solo para la 4:** el criterio 4 de la Regla 5 pide
específicamente comunicación **intra-servicio** por eventos de dominio — hoy, dentro de
`worker/main.py`, el paso de "verificación completada" a "decidir si el proveedor queda habilitado"
es una llamada directa de función. Con esta clasificación, ese paso pasa a ser: `Verificacion` emite
`VerificacionCompletada` → el dispatcher en memoria lo entrega a `ServicioDeElegibilidad` → si
corresponde, se emite el comando que termina publicando el evento de integración
`ProveedorHabilitado`. Dos módulos del mismo servicio comunicándose por evento, no por llamada
directa — eso es lo que la Regla 5.4 califica.

---

## 6. CQS — Comandos y Queries

| Comando (muta estado, no retorna datos de negocio) | Reemplaza/extiende |
|---|---|
| `IniciarVerificacion(proveedor_id, tipo_verificador)` | El cuerpo de `POST /verificaciones` |
| `RegistrarIntento(verificacion_id, resultado, error, duracion_ms)` | `actualizar_db()` en `worker/main.py` |
| `MoverADLQ(verificacion_id)` | Disparado internamente cuando `RegistrarIntento` detecta reintentos agotados |
| `ReprocesarDesdeDLQ(verificacion_id)` | El cuerpo de `POST /dlq/{id}/reprocesar` |
| `RevalidarProveedor(proveedor_id, motivo)` | **Nuevo** — exigido explícitamente por el enunciado ("Re-validaciones: periódicas, por vencimiento de certificados y por novedades de personal, un técnico nuevo... no puede atender trabajos hasta ser verificado"). `motivo` es un VO enum: `VENCIMIENTO_CERTIFICADO` \| `TECNICO_NUEVO` \| `PROGRAMADA`. Crea una nueva `Verificacion` (vía `FabricaVerificacion`) para el `proveedor_id` o `tecnico_id` afectado, dejando la anterior como historial — no la sobreescribe |

`RevalidarProveedor` se dispara de tres formas distintas: (a) un job programado (cron / Cloud
Scheduler) que revisa vencimientos de `NivelVerificacion` próximos a expirar — motivo
`VENCIMIENTO_CERTIFICADO`; (b) cuando `ProveedorEmpresa` registra un `Tecnico` nuevo — motivo
`TECNICO_NUEVO`, dispara automáticamente al guardar el técnico; (c) manual, vía endpoint, para
re-validaciones ad-hoc — motivo `PROGRAMADA`. Los tres terminan en el mismo comando, solo cambia
quién lo invoca.

| Query (solo lee) | Reemplaza/extiende |
|---|---|
| `ConsultarVerificacion(verificacion_id)` | `GET /verificaciones/{id}` |
| `ListarVerificaciones(estado?, proveedor_id?)` | `GET /verificaciones` |
| `ListarDLQ()` | `GET /dlq` |

Los *Command Handlers* viven en `application/commands/`, reciben el `IVerificacionRepository` por
constructor (inyección manual simple, no hace falta un framework de DI para este tamaño de servicio),
cargan el agregado, invocan su método de negocio, guardan, y dejan que el dispatcher reparta los
eventos de dominio acumulados. Los *Query Handlers* en `application/queries/` leen directo del
repositorio (o de una vista SQL de solo lectura si el volumen lo justificara — no es necesario a esta
escala) sin pasar por el agregado completo.

---

## 7. Kafka — tercer adaptador del puerto `Publicador`

```python
# app/common/publicador.py — clase nueva, junto a las 2 que ya existen
class PublicadorKafka(Publicador):
    def __init__(self, bootstrap_servers: str, topic_solicitudes: str, topic_fallidas: str):
        from aiokafka import AIOKafkaProducer
        self._productor = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
        self._topic_sol = topic_solicitudes
        self._topic_dlq = topic_fallidas

    async def publicar_solicitud(self, mensaje: dict) -> None:
        await self._productor.send_and_wait(
            self._topic_sol,
            json.dumps(mensaje).encode(),
            key=mensaje["proveedor_id"].encode(),  # partición por proveedor: preserva orden por proveedor
        )

    async def publicar_fallida(self, mensaje: dict) -> None:
        await self._productor.send_and_wait(self._topic_dlq, json.dumps(mensaje).encode())
```

`settings.transporte` pasa a aceptar `"rabbitmq" | "pubsub" | "kafka"`. Local: **Redpanda** (imagen
`redpandadata/redpanda`, API-compatible con Kafka, un solo contenedor, sin Zookeeper — mucho más
liviano que Kafka real para docker-compose). GCP: **Google Cloud Managed Service for Apache Kafka**
(GA desde nov. 2024, nativo de GCP — no depende de Confluent Cloud ni terceros).

**DLQ con Kafka:** no hay dead-lettering automático de broker como en RabbitMQ — se modela como el
tópico `verificacion.fallidas` (ya definido arriba), poblado por la propia aplicación cuando
`worker/core.py` agota los reintentos — exactamente la misma lógica de hoy, solo cambia el
`Publicador` que se inyecta.

---

## 8. Testing

| Herramienta | Para qué | Dónde |
|---|---|---|
| **Swagger** (`/docs`, ya generado por FastAPI) | Documentación del contrato HTTP — cero trabajo adicional | Automático |
| **pytest** (ya existe) | CP-1..CP-7 de `plan.md`, más pruebas unitarias nuevas del dominio puro (sin BD, sin HTTP) para `Verificacion`, VOs, `ServicioDeElegibilidad` | `tests/unit/dominio/` (nuevo), `tests/test_escenarios_disp03.py` (ya existe) |
| **Postman/Newman** | Colección exportable que replica CP-1..CP-6 en formato demo-able, fuera de pytest | `tests/postman/coleccion-cp1-cp6.json` |
| **JMeter** | Específicamente CP-7 (carga concurrente + falla simultánea) — percentiles de latencia de aceptación bajo volumen, que es justo la métrica de éxito de ese caso | `tests/jmeter/cp7-carga-concurrente.jmx` |

---

## 9. Observabilidad

- **Local:** `prometheus_client` expone `/metrics` en la API y el worker — contadores
  (`verificaciones_total{estado}`, `intentos_total`), histograma (`latencia_aceptacion_segundos`),
  gauge (`dlq_tamano`). `docker-compose.yml` agrega `prometheus` + `grafana`.
- **GCP:** confirmado — **Google Managed Service for Prometheus** soporta Cloud Run vía sidecar,
  mismo formato de exposición, mismos dashboards Grafana sin reescribir nada.
- **Dashboard** (`observabilidad/grafana-dashboard-disp03.json`): paneles mapeados 1:1 a la Medida de
  la respuesta de DISP-03 — disponibilidad ≥ 99.9% (gauge), tamaño de DLQ, tiempo de reproceso desde
  DLQ.

---

## 10. Checklist de la Regla 5 → evidencia exacta

| Criterio (9pt c/u) | Evidencia |
|---|---|
| 1. Patrón de dominio | `app/domain/seedwork/*`, `app/domain/verificacion/*` (agregado + entidad hija + VOs + servicio + fábrica + repositorio como interfaz) |
| 2. Hexagonal | `domain/` sin imports de infra; `application/ports/` — `IVerificacionRepository` (persistencia) e `IVerificacionExternaPort` (Policía/RUES/Certificadora) — vs. sus adaptadores en `infrastructure/persistence/` e `infrastructure/external/` |
| 3. Persistencia real | Postgres/Cloud SQL ya en uso (`models_db.py`), ahora detrás de un repositorio en vez de acceso directo desde la ruta HTTP |
| 4. Eventos de dominio intra-servicio | `domain/verificacion/eventos.py` + `application/dispatcher_eventos_dominio.py` — ver clasificación completa en sección 5 |
| 5. CQS | `application/commands/*` vs. `application/queries/*`, tabla sección 6 |

---

## 11. Fases de implementación

1. Seedwork + agregado `Verificacion` + entidad `IntentoVerificacion` + VOs — con pruebas unitarias, sin tocar nada de infraestructura.
2. `ServicioDeElegibilidad` + `FabricaVerificacion` + `IVerificacionRepository` (interfaz).
3. `verificacion_repository_sqlalchemy.py` — implementación real sobre la tabla existente + migración para `intentos_verificacion`.
4. `application/commands/*` y `application/queries/*`.
5. Refactor de `app/api/main.py` para llamar a la capa de aplicación en vez de tocar el ORM directo; refactor de `app/worker/core.py` para llamar a `IVerificacionExternaPort` en vez de `httpx` directo, con sus 3 adaptadores (`AdaptadorPolicia`, `AdaptadorRUES`, `AdaptadorCertificadora`).
6. `dispatcher_eventos_dominio.py` + clasificación de eventos (sección 5) implementada en código.
7. `PublicadorKafka` + Redpanda en docker-compose + settings nuevos.
8. Observabilidad (`prometheus_client` + dashboard).
9. Postman/Newman + JMeter.
10. Actualizar `README.md` de `../implementacion/DISP-03/` quitando la sección "Servicio DDD — todavía no implementado aquí".
