# Gestión de Trabajos

**Estado: esqueleto inicial (skeleton), no implementación completa.** Este documento es honesto a
propósito sobre qué falta — lo termina una persona real del equipo (ver sección "Qué falta" al
final). Construido según el runbook de Frans en
`experimento-arquitectura/contexto/12-plan-entrega-4.md` (sección 8) y las reglas de
`.claude/agents/implementador-ddd.md`.

**Separación de Pagos (posterior a la construcción inicial de este servicio)**: el módulo ACL de
Pagos que originalmente vivía aquí (agregado `Pago`, Strategy `ReglaRegional`, Adapter
`IPasarelaDePago`) se extrajo a su propio microservicio independiente en
`experimento-arquitectura/implementacion/pagos/` — ver el README.md de ese servicio, sección
"Frontera del API", para el detalle de qué cableado cambió al separar el proceso. Este documento
ya refleja ese estado posterior a la separación, no el original.

## Qué es este servicio

Microservicio propio (Bounded Context independiente, ver `03-contextos-acotados-TO-BE.cml`) que
crea un `Trabajo` (agregado raíz, ya definido como tal en `07-vista-informacion.puml`) y publica
el evento de integración `trabajos.finalizado` hacia Apache Pulsar — es el disparador de la
transacción larga de la Entrega 4 (Gestión de Trabajos → Proveedores → Reputación).

## Estructura (arquitectura hexagonal)

```
app/
  domain/               ← sin imports de FastAPI, SQLAlchemy, pulsar-client, httpx ni tenacity
    seedwork/           ← Entity, AggregateRoot, DomainEvent, ValueObject, IRepository (propios de este BC)
    trabajo/            ← agregado Trabajo, eventos, VOs, repositorio (puerto), fábrica
    novedades/          ← agregado Novedad (DISP-02), eventos, VOs, repositorio (puerto), fábrica
  application/
    ports/              ← IPublicador, IRegistroTrabajosRepository, IGestionAgentesPort (interfaces
                           que implementa infrastructure/)
    commands/           ← CrearTrabajo, PublicarNovedad (mutan, retornan solo un id — CQS)
    queries/            ← ConsultarTrabajo, ConsultarNovedad (solo leen)
    dispatcher_eventos_dominio.py  ← despachador en memoria de eventos de dominio de Trabajo
  infrastructure/
    persistence/        ← modelos SQLAlchemy (tablas `trabajos`, `trabajos_elegibles_pago`,
                           `novedades`) + repositorios concretos
    messaging/           ← PublicadorPulsar (integración hacia Pulsar); ThrottlerCrm (Sidecar de
                           DISP-02: cola en memoria + token bucket + reintentos hacia el CRM)
    adapters/            ← AdaptadorGestionAgentesHttp (adaptador HTTP de IGestionAgentesPort hacia
                           el mock del CRM "Gestión de Agentes")
  common/                ← config (Pydantic Settings), db (engine/sesión SQLAlchemy), schemas HTTP, logging
  api/main.py            ← FastAPI; solo llama a application/commands y application/queries
tests/unit/
  dominio/               ← pruebas de dominio puro, sin BD/Pulsar/HTTP (Trabajo, Novedad)
  aplicacion/            ← pruebas del dispatcher y del ThrottlerCrm con fakes en memoria
tests/integracion/
  test_disp02_throttler.py  ← prueba de carga end-to-end de DISP-02 contra Postgres real + el
                               mock real del CRM (implementacion/mocks-crm/), ver sección DISP-02
```

Separación de Pagos: `domain/pagos/`, `application/commands/{pagar_trabajo,compensar}.py`,
`application/queries/consultar_pago.py`, `application/ports/{pasarela_de_pago,registro_trabajos}.py`
(el puerto en sí se queda, ver más abajo) e `infrastructure/adapters/` ya NO viven aquí — se
movieron a `implementacion/pagos/`.

Regla no negociable verificada: `domain/` no importa nada de `sqlalchemy`, `fastapi` ni
`pulsar-client`; `application/` solo importa `domain/` y sus propios puertos; `api/main.py` no toca
el ORM ni el agregado directo, solo comandos/queries.

## Eventos: dominio vs. integración (distinción explícita, Regla 4)

- **Evento de DOMINIO**: `TrabajoFinalizado` (`domain/trabajo/eventos.py`) — nace dentro del
  agregado `Trabajo.finalizar()`, nunca importa nada de Pulsar, nunca cruza el proceso por sí solo.
- **Evento de INTEGRACIÓN**: el mensaje Avro que `PublicadorPulsar` efectivamente publica en el
  tópico `trabajos.finalizado` de Pulsar. La traducción dominio→integración ocurre en
  `application/dispatcher_eventos_dominio.py` — es la capa de aplicación quien decide publicar,
  nunca el dominio.
- **Reacción intra-servicio**: `CrearTrabajo` no recoge y publica el evento inline — le pasa
  `trabajo.recoger_eventos()` al dispatcher, que reacciona a `TrabajoFinalizado` de dos formas: (1)
  publica el evento de integración hacia Pulsar, y (2) puebla el registro local
  `IRegistroTrabajosRepository` (`application/ports/registro_trabajos.py`, tabla
  `trabajos_elegibles_pago`) con lo que se sabe del trabajo.
- **Separación de Pagos (cambio de alcance de esta reacción)**: antes de que Pagos fuera un
  microservicio aparte, este mismo registro era la vía por la que el módulo Pagos (entonces
  submódulo de este proceso) se enteraba de un `TrabajoFinalizado` sin acoplarse al repositorio del
  agregado `Trabajo` — comunicación intra-servicio por eventos de dominio (Regla 5, criterio 4).
  Ahora que Pagos es OTRO proceso, ya no lee este registro (recibe los mismos datos por HTTP en
  `POST /pagos` de ese servicio — ver `implementacion/pagos/README.md`, sección "Frontera del
  API"); el registro se conserva aquí solo como trazabilidad local de este servicio, y la reacción
  del dispatcher sigue siendo un ejemplo válido de "agregado → evento de dominio → reacción
  desacoplada", aunque ya no alimente a otro módulo interno.

## Cómo correrlo (local, sin Docker Compose todavía en esta carpeta)

```bash
cd experimento-arquitectura/implementacion/gestion-de-trabajos
python -m venv .venv && source .venv/Scripts/activate  # o .venv/bin/activate en Linux/Mac
pip install -r requirements.txt

# Variables de entorno mínimas (o usar los defaults de app/common/config.py):
export DATABASE_URL="postgresql+psycopg2://hda:hda@localhost:5432/gestion_trabajos"
export PULSAR_SERVICE_URL="pulsar://localhost:6650"

uvicorn app.api.main:app --reload --port 8001
```

Requiere una Postgres real accesible en `DATABASE_URL` (crea las tablas `trabajos`/
`trabajos_elegibles_pago` al arrancar, vía `Base.metadata.create_all()`) y, para que
`POST /trabajos` no falle al publicar el
evento, un cluster de Pulsar accesible en `PULSAR_SERVICE_URL` — lo construye Daniel en
`implementacion/pulsar-infra/`. El cliente de Pulsar se conecta de forma perezosa (solo al primer
publish), así que la API puede levantarse igual sin el cluster arriba; solo falla (y lo loguea,
sin tumbar el request) el intento de publicación.

## Endpoints

- `POST /trabajos` — comando `CrearTrabajo`. Body: `{proveedor_id, monto, region}` (`region`: `"CO"`
  o `"BR"`). Retorna `{id}` (CQS: nunca el estado completo).
- `GET /trabajos/{id}` — query `ConsultarTrabajo`.
- `POST /novedades` — comando `PublicarNovedad` (DISP-02, ver sección siguiente). Body:
  `{trabajo_id, descripcion}`. Responde **202 Accepted** de inmediato con `{id}` — la entrega real al
  CRM es asíncrona, vía el `ThrottlerCrm` en background.
- `GET /novedades/{id}` — query `ConsultarNovedad` (agregado junto con la prueba de carga de DISP-02
  para poder sondear el estado del agregado desde fuera del proceso).
- `GET /salud`.

Los endpoints `/pagos*` que antes vivían aquí (`POST /pagos`, `GET /pagos/{id}`,
`POST /pagos/{id}/compensar`) se movieron al microservicio `implementacion/pagos/`.

## DISP-02: Sidecar/Throttler hacia el CRM "Gestión de Agentes"

Ver `escenarios_calidad.md`, fila DISP-02, para el escenario completo. Mecanismo implementado:

1. `POST /novedades` → `PublicarNovedad.ejecutar()` crea la `Novedad` (agregado raíz propio, ver
   `domain/novedades/novedad.py` y la nota de inconsistencia con `07-vista-informacion.puml` en su
   docstring), la persiste como `PENDIENTE` y la encola en `ThrottlerCrm.encolar()` — un
   `await queue.put(...)` que no ejecuta ninguna llamada de red y responde de inmediato.
2. `ThrottlerCrm` (`infrastructure/messaging/throttler.py`) consume la cola con un único worker en
   background (arrancado en `startup` de FastAPI, cancelado limpio en `shutdown`), dosificado por un
   token bucket a `settings.crm_limite_rps` (default 50 rps).
3. Cada intento llama a `IGestionAgentesPort.enviar_webhook` (puerto), resuelto por
   `AdaptadorGestionAgentesHttp` (`infrastructure/adapters/throttler_crm.py`) hacia
   `settings.crm_mock_url` — el doble del CRM lo construye otro agente en
   `implementacion/mocks-crm/`.
4. Ante un `429`/error transitorio, reintenta con backoff exponencial + jitter (`tenacity.wait_exponential_jitter`,
   respetando `Retry-After` si el CRM lo manda) hasta `settings.throttler_max_reintentos` intentos.
   Al agotarlos, llama `Novedad.marcar_agotada()` en vez de perderla en silencio; al tener éxito,
   `Novedad.marcar_entregada()`. Ambas transiciones producen eventos de DOMINIO
   (`NovedadEntregada`/`NovedadAgotada`, `domain/novedades/eventos.py`) — distintos de la llamada
   HTTP en sí (esa es la integración saliente hacia el CRM externo, ver el docstring de esos
   archivos para la distinción completa, Regla 4).

Nombres exactos de configuración (`app/common/config.py`) que usa la prueba de carga y el mock del
CRM: `crm_mock_url`, `crm_limite_rps` (default `50.0`), `throttler_cola_tamano` (default `10_000` —
ver cálculo de dimensionamiento para absorber un pico de 4x en el docstring de `throttler.py`),
`throttler_max_reintentos` (default `5`), `throttler_backoff_base_s` (default `0.5`),
`throttler_backoff_max_s` (default `30.0`).

### Mock del CRM y prueba de carga end-to-end (validado en esta sesión)

El doble real del CRM "Gestión de Agentes" vive en `implementacion/mocks-crm/` — a diferencia de los
mocks de DISP-03/Pagos (que simulan latencia/fallas), este hace cumplir un **límite de tasa real**
(ventana deslizante de 1s) sobre `POST /webhooks`, respondiendo `429` + `Retry-After` cuando se
supera. Se controla en caliente vía `POST /_control/config` (`{"limite_rps": N}`), mismo patrón que
los demás mocks del repo.

`docker-compose.disp02.yml` (en esta carpeta) orquesta el escenario completo — Postgres + esta API +
`mock-crm` — en la misma red de compose, para que la API alcance al mock por nombre de servicio:

```bash
cd experimento-arquitectura/implementacion/gestion-de-trabajos
docker compose -f docker-compose.disp02.yml up -d --build
pytest tests/integracion/test_disp02_throttler.py -v
docker compose -f docker-compose.disp02.yml down -v
```

`tests/integracion/test_disp02_throttler.py` dispara una ráfaga real de 2.000 `POST /novedades`
concurrentes (>4x el límite del CRM mock, 20 rps) y confirma que el 100% termina `ENTREGADA` dentro
de los umbrales de tiempo de DISP-02 (medido, no comprimido: ≈2min de drenado real, muy por debajo
de los 15min/1h del umbral) — resultado y parámetros finales completos, incluyendo las 2 iteraciones
de ajuste que hicieron falta antes de pasar (capacidad de ingesta de la API, no el mecanismo de
throttling en sí), en `../RESULTADOS-DISP02.md` y en el JSONL de datos crudos
`tests/integracion/results/resultados_disp02.jsonl`. El veredicto de si esto valida o refuta la
hipótesis de DISP-02 es responsabilidad de `validador-hipotesis`, no de este README.

## Tests

```bash
pip install -r requirements.txt
pytest tests/unit -v
```

`tests/unit/dominio/` no requiere BD, Pulsar ni HTTP — prueba `Trabajo` y `Novedad` en aislamiento
(invariantes de transición de estado de ambos agregados).
`tests/unit/aplicacion/` prueba el dispatcher de `Trabajo` y el `ThrottlerCrm` con fakes en memoria
(sin BD, sin Pulsar, sin HTTP real tampoco — el fake de `IGestionAgentesPort` simula éxito/429 sin
llamar a `httpx`).

`tests/integracion/test_disp02_throttler.py` **sí** corre contra Postgres real y el mock real del CRM
(`implementacion/mocks-crm/`) — requiere `docker-compose.disp02.yml` arriba (ver sección DISP-02
arriba). No requiere Pulsar real (sigue sin haber una prueba de integración contra el cluster de
Pulsar de Daniel).

## Los 5 criterios de la Regla 5 (`REGLAS-DURAS-rubrica-entrega-3.md`) — qué quedó cubierto

Nota: esta tabla cubre solo lo que se quedó en `gestion-de-trabajos` tras la separación de Pagos.
Para la evaluación equivalente del microservicio Pagos, ver `implementacion/pagos/README.md`.

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Patrón de dominio | **Cubierto, con una brecha señalada por auditoría** | `domain/seedwork/` (Entity, AggregateRoot, DomainEvent, ValueObject, IRepository); dos agregados con raíz clara (`Trabajo`, `Novedad`); VOs (`Dinero`, `Region`, `TrabajoId`, `NovedadId`, `EstadoNovedad`, etc.); fábricas (`FabricaTrabajo`, `FabricaNovedad`); repositorios como puertos (`ITrabajoRepository`, `INovedadRepository`). **Pendiente**: `rubrica-auditor` señaló que ningún agregado tiene una entidad hija real (distinta de la raíz) — `Novedad` tampoco la tiene, sigue sin corregirse en este ciclo, ver "Qué falta" |
| 2 | Arquitectura hexagonal | **Cubierto** | Verificado por import real (no solo nombres de carpeta, ver chequeo de imports corrido en esta sesión): `domain/` no importa sqlalchemy/fastapi/pulsar-client/httpx/tenacity; `application/` solo importa `domain/` y sus puertos (`IGestionAgentesPort` incluido); `api/main.py` solo llama comandos/queries; el adaptador HTTP (`AdaptadorGestionAgentesHttp`) y el Throttler (`ThrottlerCrm`) viven en `infrastructure/`, nunca en `domain/` ni `application/` |
| 3 | Persistencia real | **Cubierto** | Postgres vía SQLAlchemy (`models_db.py`, tablas `trabajos`/`trabajos_elegibles_pago`/`novedades`), repositorios concretos en `infrastructure/persistence/` (`TrabajoRepositorySQLAlchemy`, `NovedadRepositorySQLAlchemy`). **Pendiente de verificar en este ciclo**: no se corrió una prueba de integración contra una Postgres real (no había una levantada en este entorno de trabajo) — el mapeo se revisó por lectura de código y por `pytest tests/unit`, no ejecutado end-to-end contra una BD real |
| 4 | Eventos de dominio intra-servicio | **Cubierto** | `application/dispatcher_eventos_dominio.py` reacciona a `TrabajoFinalizado` (publica el evento de integración y puebla el registro local `trabajos_elegibles_pago`). Para DISP-02, `Novedad.marcar_entregada()`/`marcar_agotada()` producen los eventos de dominio `NovedadEntregada`/`NovedadAgotada` (`domain/novedades/eventos.py`), explícitamente distintos de la llamada HTTP de integración hacia el CRM que el `ThrottlerCrm` hace a través de `IGestionAgentesPort` — ver docstrings de esos dos archivos para la distinción dominio/integración (Regla 4). **Nota**: en este ciclo ningún otro módulo se suscribe todavía a `NovedadEntregada`/`NovedadAgotada` (no hay, por ejemplo, un módulo de "aprobación" o "auditoría de entregas" reaccionando) — el agregado los produce igual, listos para un suscriptor futuro, pero la demostración de "reacción de otro módulo" solo está completa para `TrabajoFinalizado` |
| 5 | CQS | **Cubierto** | Los comandos `CrearTrabajo` y `PublicarNovedad` retornan solo un `id`, nunca el agregado ni su estado de negocio (`PublicarNovedad` además responde `202 Accepted`, dejando explícito que la entrega real es asíncrona); la query `ConsultarTrabajo` solo lee, nunca muta — separación visible en carpetas `commands/` vs `queries/` |

## Qué falta (para quien complete este servicio)

- **Prueba de integración real** contra Postgres (y, si el cluster de Daniel ya está arriba, contra
  Pulsar real) — no se hizo en esta sesión por no tener ninguno de los dos disponible en este
  entorno de trabajo.
- **Criterio 1 (patrón de dominio)**: `rubrica-auditor` encontró que ningún agregado tiene una
  entidad hija real (distinta de la raíz) — no se corrigió en este ciclo.
- **Consumidor de eventos**: este servicio solo publica (`trabajos.finalizado`); no consume nada de
  Proveedores/Reputación en este skeleton — no hace falta según el alcance de la Entrega 4 (sección
  1.1 del plan: "los servicios deben poder oírse... pero no deben reaccionar todavía").
- **`07-vista-informacion.puml` no modela a `Trabajo` con los atributos usados aquí** (ver docstring
  de `domain/trabajo/trabajo.py`) — es una inconsistencia esperable, pero vale la pena que
  `disenador-escenarios` decida si actualizar el diagrama o dejarlo explícitamente fuera de su
  alcance.
- **Migraciones formales (Alembic)**: no hay, igual que en DISP-03 — `Base.metadata.create_all()`
  basta para este PoC.
- **Comunicación real con el microservicio Pagos**: hoy Pagos no consume ningún evento de este
  servicio — recibe los datos del trabajo por HTTP directamente en su propio `POST /pagos` (ver
  `implementacion/pagos/README.md`, sección "Frontera del API"). Diseñar un consumidor real en
  Pagos sobre el tópico `trabajos.finalizado` es el siguiente paso natural.
- **`docker-compose.yml` propio de este servicio**: no se creó — se asume que la Postgres y el
  cluster de Pulsar los levanta la infraestructura común del proyecto (`implementacion/pulsar-infra/`
  para Pulsar; Postgres se puede compartir con el `docker-compose.yml` de DISP-03 apuntando a otra
  base de datos, o crear uno nuevo — decisión de equipo pendiente).
- **DISP-02/`ThrottlerCrm` — limitaciones explícitas de este ciclo** (no se corrigieron por no estar
  ancladas a un requisito ya exigido, ver notas en `infrastructure/messaging/throttler.py`):
  - Cola (`asyncio.Queue`) **en memoria, dentro del propio proceso** — si el proceso muere con
    novedades ya encoladas pero sin persistir su resultado final, esas novedades se pierden del
    Throttler (aunque siguen en Postgres como `PENDIENTE`). `INovedadRepository.listar_pendientes()`
    ya existe como puerto para reconstruir la cola al reiniciar, pero **no hay todavía** un
    `startup` que la llame — es la pieza que falta para no depender de que el proceso nunca muera
    con trabajo en vuelo.
  - **Un único worker secuencial**: el backoff de una `Novedad` que falla retrasa a las que le
    siguen en la cola durante esa espera. Escalar a N workers concurrentes (cada uno con su propio
    recorte del token bucket compartido) es la extensión natural si el experimento de carga muestra
    que un solo worker no sostiene la tasa objetivo.
  - **Token bucket de un solo proceso**: si el servicio corre con más de una réplica, cada una
    aplicaría su propio límite de `crm_limite_rps` de forma independiente, sumando más tráfico real
    hacia el CRM del que espera `settings.crm_limite_rps` — un límite compartido correcto entre
    réplicas necesitaría un token bucket centralizado (p.ej. Redis), fuera de alcance de este PoC.
  - **[Cerrado en esta sesión]** Ya existe una prueba de integración de `AdaptadorGestionAgentesHttp`
    contra el mock real del CRM (`implementacion/mocks-crm/`) — `tests/integracion/
    test_disp02_throttler.py`, corrida contra `docker-compose.disp02.yml`. Los datos crudos (100% de
    2.000 novedades entregadas en ≈2min de drenado real, 0 pérdida por rate limiting) están en
    `../RESULTADOS-DISP02.md`; el veredicto sobre si eso valida la hipótesis de DISP-02 lo da
    `validador-hipotesis`, no este README. Sigue pendiente: correr esto contra GCP real (solo se
    corrió local) y extender `mocks-crm` con modos `caido`/`timeout` (hoy solo modela rate limiting,
    no una caída dura del CRM).
  - **`07-vista-informacion.puml` no modela a `Novedad` como agregado raíz propio** (la dibuja como
    entidad hija de `Trabajo`, sin atributos) — ver la nota de inconsistencia explícita en el
    docstring de `domain/novedades/novedad.py`; queda pendiente que `disenador-escenarios` decida si
    actualizar el diagrama.
