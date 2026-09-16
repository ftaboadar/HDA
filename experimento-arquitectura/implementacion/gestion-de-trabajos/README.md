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
  domain/               ← sin imports de FastAPI, SQLAlchemy ni pulsar-client
    seedwork/           ← Entity, AggregateRoot, DomainEvent, ValueObject, IRepository (propios de este BC)
    trabajo/            ← agregado Trabajo, eventos, VOs, repositorio (puerto), fábrica
  application/
    ports/              ← IPublicador, IRegistroTrabajosRepository (interfaces que implementa
                           infrastructure/)
    commands/           ← CrearTrabajo (muta, retorna solo un id — CQS)
    queries/            ← ConsultarTrabajo (solo lee)
    dispatcher_eventos_dominio.py  ← despachador en memoria de eventos de dominio de Trabajo
  infrastructure/
    persistence/        ← modelos SQLAlchemy (tablas `trabajos`, `trabajos_elegibles_pago`) +
                           repositorios concretos
    messaging/           ← PublicadorPulsar (adaptador de integración hacia Pulsar)
  common/                ← config (Pydantic Settings), db (engine/sesión SQLAlchemy), schemas HTTP, logging
  api/main.py            ← FastAPI; solo llama a application/commands y application/queries
tests/unit/
  dominio/               ← pruebas de dominio puro, sin BD/Pulsar/HTTP
  aplicacion/            ← pruebas del dispatcher con fakes en memoria
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
- `GET /salud`.

Los endpoints `/pagos*` que antes vivían aquí (`POST /pagos`, `GET /pagos/{id}`,
`POST /pagos/{id}/compensar`) se movieron al microservicio `implementacion/pagos/`.

## Tests

```bash
pip install -r requirements.txt
pytest tests/unit -v
```

`tests/unit/dominio/` no requiere BD, Pulsar ni HTTP — prueba `Trabajo` en aislamiento.
`tests/unit/aplicacion/` prueba el dispatcher con fakes en memoria (sin BD ni Pulsar tampoco). No
hay todavía una prueba de integración con Postgres/Pulsar reales (ver "Qué falta").

## Los 5 criterios de la Regla 5 (`REGLAS-DURAS-rubrica-entrega-3.md`) — qué quedó cubierto

Nota: esta tabla cubre solo lo que se quedó en `gestion-de-trabajos` tras la separación de Pagos.
Para la evaluación equivalente del microservicio Pagos, ver `implementacion/pagos/README.md`.

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Patrón de dominio | **Cubierto, con una brecha señalada por auditoría** | `domain/seedwork/` (Entity, AggregateRoot, DomainEvent, ValueObject, IRepository); agregado `Trabajo` con raíz clara; VOs (`Dinero`, `Region`, `TrabajoId`, etc.); fábrica (`FabricaTrabajo`); repositorio como puerto (`ITrabajoRepository`). **Pendiente**: `rubrica-auditor` señaló que ningún agregado tiene una entidad hija real (distinta de la raíz) — no se corrigió en este ciclo, ver "Qué falta" |
| 2 | Arquitectura hexagonal | **Cubierto** | Verificado por import real (no solo nombres de carpeta): `domain/` no importa sqlalchemy/fastapi/pulsar-client; `application/` solo importa `domain/` y sus puertos; `api/main.py` solo llama comandos/queries |
| 3 | Persistencia real | **Cubierto** | Postgres vía SQLAlchemy (`models_db.py`, tablas `trabajos`/`trabajos_elegibles_pago`), repositorio concreto en `infrastructure/persistence/`. **Pendiente de verificar en este ciclo**: no se corrió una prueba de integración contra una Postgres real (no había una levantada en este entorno de trabajo) — el mapeo se revisó por lectura de código, no ejecutado end-to-end |
| 4 | Eventos de dominio intra-servicio | **Cubierto para lo que queda en este servicio; la reacción intra-servicio original ya no aplica tras separar Pagos** | `application/dispatcher_eventos_dominio.py` reemplaza el recoger+publicar inline que había antes; sigue reaccionando a `TrabajoFinalizado` publicando el evento de integración y poblando el registro local `trabajos_elegibles_pago`. La reacción que antes alimentaba al módulo Pagos (entonces submódulo de este proceso) ya no aplica: Pagos es ahora otro microservicio y recibe esos datos por HTTP, no por evento de dominio intra-proceso — ver `implementacion/pagos/README.md` |
| 5 | CQS | **Cubierto** | El comando `CrearTrabajo` retorna solo un `id`, nunca el agregado ni su estado de negocio; la query `ConsultarTrabajo` solo lee, nunca muta — separación visible en carpetas `commands/` vs `queries/` |

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
