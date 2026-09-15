# Gestión de Trabajos (+ módulo ACL de Pagos)

**Estado: esqueleto inicial (skeleton), no implementación completa.** Este documento es honesto a
propósito sobre qué falta — lo termina una persona real del equipo (ver sección "Qué falta" al
final). Construido según el runbook de Frans en
`experimento-arquitectura/contexto/12-plan-entrega-4.md` (sección 8) y las reglas de
`.claude/agents/implementador-ddd.md`.

## Qué es este servicio

Microservicio propio (Bounded Context independiente, ver `03-contextos-acotados-TO-BE.cml`) que:

1. **Núcleo Trabajo**: crea un `Trabajo` (agregado raíz, ya definido como tal en
   `07-vista-informacion.puml`) y publica el evento de integración `trabajos.finalizado` hacia
   Apache Pulsar — es el disparador de la transacción larga de la Entrega 4
   (Gestión de Trabajos → Proveedores → Reputación).
2. **Módulo ACL de Pagos**: submódulo de este mismo servicio (NO un microservicio aparte — ver
   `12-plan-entrega-4.md` sección 0.1: `Pagos` es un `GENERIC_SUBDOMAIN` externo, sin
   `BoundedContext` propio). Implementa el patrón Strategy (`ReglaRegional`) y el patrón Adapter
   (`IPasarelaDePago`) para cobrar/compensar contra mocks HTTP de Stripe/MercadoPago.

## Estructura (arquitectura hexagonal)

```
app/
  domain/               ← sin imports de FastAPI, SQLAlchemy ni pulsar-client
    seedwork/           ← Entity, AggregateRoot, DomainEvent, ValueObject, IRepository (propios de este BC)
    trabajo/            ← agregado Trabajo, eventos, VOs, repositorio (puerto), fábrica
    pagos/              ← agregado Pago, VOs, repositorio (puerto), Strategy ReglaRegional, fábrica
  application/
    ports/              ← IPublicador, IPasarelaDePago, IRegistroTrabajosRepository (interfaces
                           que implementa infrastructure/)
    commands/           ← CrearTrabajo, PagarTrabajo, Compensar (mutan, retornan solo un id — CQS)
    queries/            ← ConsultarTrabajo, ConsultarPago (solo leen)
    dispatcher_eventos_dominio.py  ← despachador en memoria de eventos de dominio (Trabajo y Pago)
  infrastructure/
    persistence/        ← modelos SQLAlchemy (tablas `trabajos`, `pagos`, `trabajos_elegibles_pago`)
                           + repositorios concretos
    messaging/           ← PublicadorPulsar (adaptador de integración hacia Pulsar)
    adapters/            ← ReglaColombia/ReglaBrasil (Strategy), PasarelaStripe/PasarelaMercadoPago (Adapter)
  common/                ← config (Pydantic Settings), db (engine/sesión SQLAlchemy), schemas HTTP, logging
  api/main.py            ← FastAPI; solo llama a application/commands y application/queries
tests/unit/
  dominio/               ← pruebas de dominio puro, sin BD/Pulsar/HTTP
  aplicacion/            ← pruebas del dispatcher con fakes en memoria
```

Regla no negociable verificada: `domain/` no importa nada de `sqlalchemy`, `fastapi` ni
`pulsar-client`; `application/` solo importa `domain/` y sus propios puertos; `api/main.py` no toca
el ORM ni el agregado directo, solo comandos/queries.

## Eventos: dominio vs. integración (distinción explícita, Regla 4)

- **Evento de DOMINIO**: `TrabajoFinalizado` (`domain/trabajo/eventos.py`) — nace dentro del
  agregado `Trabajo.finalizar()`, nunca importa nada de Pulsar, nunca cruza el proceso por sí solo.
  `Pago` también registra los suyos (`domain/pagos/eventos.py`: `PagoMarcadoExitoso`,
  `PagoMarcadoFallido`, `PagoCompensado`) en sus transiciones de estado.
- **Evento de INTEGRACIÓN**: el mensaje Avro que `PublicadorPulsar` efectivamente publica en el
  tópico `trabajos.finalizado` de Pulsar. La traducción dominio→integración ocurre en
  `application/dispatcher_eventos_dominio.py` — es la capa de aplicación quien decide publicar,
  nunca el dominio.
- **Reacción intra-servicio (ya no es una limitación, corregido)**: `CrearTrabajo` ya no recoge y
  publica el evento inline — le pasa `trabajo.recoger_eventos()` al dispatcher, que tiene DOS
  reacciones para `TrabajoFinalizado`: (1) publica el evento de integración hacia Pulsar, y (2)
  puebla el registro `IRegistroTrabajosRepository` del módulo Pagos
  (`application/ports/registro_trabajos.py`) con lo que ese módulo necesita saber del trabajo. Antes,
  `PagarTrabajo` recibía `ITrabajoRepository` (el repositorio del OTRO módulo) inyectado
  directamente; ahora depende solo de ese registro, poblado exclusivamente vía el evento de dominio
  — mismo patrón que `ServicioDeElegibilidad` en DISP-03 (agregado → evento dominio → OTRO módulo
  reacciona → decide publicar integración), adaptado a que aquí la reacción intra-servicio no
  necesitaba un servicio de dominio propio, sino un registro/ACL poblado por el dispatcher.

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

Requiere una Postgres real accesible en `DATABASE_URL` (crea las tablas `trabajos`/`pagos` al
arrancar, vía `Base.metadata.create_all()`) y, para que `POST /trabajos` no falle al publicar el
evento, un cluster de Pulsar accesible en `PULSAR_SERVICE_URL` — lo construye Daniel en
`implementacion/pulsar-infra/`. El cliente de Pulsar se conecta de forma perezosa (solo al primer
publish), así que la API puede levantarse igual sin el cluster arriba; solo falla (y lo loguea,
sin tumbar el request) el intento de publicación.

## Endpoints

- `POST /trabajos` — comando `CrearTrabajo`. Body: `{proveedor_id, monto, region}` (`region`: `"CO"`
  o `"BR"`). Retorna `{id}` (CQS: nunca el estado completo).
- `GET /trabajos/{id}` — query `ConsultarTrabajo`.
- `POST /pagos` — comando `PagarTrabajo`. Body: `{trabajo_id, pasarela}` (`pasarela`: `"stripe"` o
  `"mercadopago"`). Resuelve la `ReglaRegional` según la región del trabajo y llama al mock HTTP
  correspondiente.
- `GET /pagos/{id}` — query `ConsultarPago`.
- `POST /pagos/{id}/compensar` — comando `Compensar`.

## Tests

```bash
pip install -r requirements.txt
pytest tests/unit -v
```

`tests/unit/dominio/` no requiere BD, Pulsar ni HTTP — prueba `Trabajo`, `Pago` y `ReglaRegional`
en aislamiento. `tests/unit/aplicacion/` prueba el dispatcher con fakes en memoria (sin BD ni
Pulsar tampoco). No hay todavía una prueba de integración con Postgres/Pulsar reales (ver "Qué
falta").

## Los 5 criterios de la Regla 5 (`REGLAS-DURAS-rubrica-entrega-3.md`) — qué quedó cubierto

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Patrón de dominio | **Cubierto, con una brecha señalada por auditoría** | `domain/seedwork/` (Entity, AggregateRoot, DomainEvent, ValueObject, IRepository); agregados `Trabajo`/`Pago` con raíz clara; VOs (`Dinero`, `Region`, `TrabajoId`, etc.); fábricas (`FabricaTrabajo`, `FabricaPago`); repositorios como puertos (`ITrabajoRepository`, `IPagoRepository`). **Pendiente**: `rubrica-auditor` señaló que `ReglaRegional` como Strategy es discutible como "servicio de dominio" en el sentido estricto de la rúbrica (orquestar entre múltiples agregados, como sí hace `ServicioDeElegibilidad` en DISP-03), y que ningún agregado tiene una entidad hija real (distinta de la raíz) — no se corrigió en este ciclo, ver "Qué falta" |
| 2 | Arquitectura hexagonal | **Cubierto** | Verificado por import real (no solo nombres de carpeta): `domain/` no importa sqlalchemy/fastapi/pulsar-client; `application/` solo importa `domain/` y sus puertos; `api/main.py` solo llama comandos/queries |
| 3 | Persistencia real | **Cubierto** | Postgres vía SQLAlchemy (`models_db.py`, tablas `trabajos`/`pagos`/`trabajos_elegibles_pago`), repositorios concretos en `infrastructure/persistence/`. **Pendiente de verificar en este ciclo**: no se corrió una prueba de integración contra una Postgres real (no había una levantada en este entorno de trabajo) — el mapeo se revisó por lectura de código, no ejecutado end-to-end |
| 4 | Eventos de dominio intra-servicio | **Cubierto (corregido tras auditoría, dos rondas)** | `application/dispatcher_eventos_dominio.py` reemplaza el recoger+publicar inline que había antes. `Pago` ahora también registra eventos (`PagoMarcadoExitoso`/`PagoMarcadoFallido`/`PagoCompensado`, antes no registraba ninguno). Comunicación real entre módulos DEL MISMO servicio: `PagarTrabajo` ya no recibe `ITrabajoRepository` (el repositorio del módulo Trabajo) inyectado — depende solo de `IRegistroTrabajosRepository`, poblado exclusivamente por el dispatcher al reaccionar a `TrabajoFinalizado`. Segunda ronda de auditoría encontró que `Compensar` generaba `PagoCompensado` pero nunca lo recogía/despachaba (se perdía en silencio) — corregido: `Compensar.ejecutar()` ahora es async y despacha, igual que `PagarTrabajo`. Probado en `tests/unit/aplicacion/{test_dispatcher_eventos_dominio,test_compensar}.py` |
| 5 | CQS | **Cubierto** | Comandos (`CrearTrabajo`, `PagarTrabajo`, `Compensar`) retornan solo un `id`, nunca el agregado ni su estado de negocio; queries (`ConsultarTrabajo`, `ConsultarPago`) solo leen, nunca mutan — separación visible en carpetas `commands/` vs `queries/` |

## Qué falta (para quien complete este servicio)

- **Prueba de integración real** contra Postgres (y, si el cluster de Daniel ya está arriba, contra
  Pulsar real) — no se hizo en esta sesión por no tener ninguno de los dos disponible en este
  entorno de trabajo.
- **Criterio 1 (patrón de dominio)**: `rubrica-auditor` encontró dos brechas menores que no se
  cerraron en este ciclo (se priorizó el criterio 4, de mayor riesgo) — evaluar si vale la pena un
  servicio de dominio inequívoco (más allá del Strategy `ReglaRegional`) y/o modelar una entidad
  hija real en algún agregado.
- **Reversa real en la pasarela externa** al compensar: `Compensar` (ver
  `application/commands/compensar.py`) solo marca el estado de dominio; `IPasarelaDePago` solo
  define `cobrar()`, no `reversar()` — agregarlo depende de que el mock de Johan
  (`implementacion/mocks-pagos/`) soporte ese endpoint.
- **Consumidor de eventos**: este servicio solo publica (`trabajos.finalizado`); no consume nada de
  Proveedores/Reputación en este skeleton — no hace falta según el alcance de la Entrega 4 (sección
  1.1 del plan: "los servicios deben poder oírse... pero no deben reaccionar todavía").
- **`07-vista-informacion.puml` no modela a `Trabajo` con los atributos usados aquí** (ver docstring
  de `domain/trabajo/trabajo.py`) ni contiene ninguna entidad `Pago` — es una inconsistencia
  esperable dado que Pagos es `GENERIC_SUBDOMAIN` externo, pero vale la pena que
  `disenador-escenarios` decida si actualizar el diagrama o dejarlo explícitamente fuera de su
  alcance.
- **Migraciones formales (Alembic)**: no hay, igual que en DISP-03 — `Base.metadata.create_all()`
  basta para este PoC.
- **`docker-compose.yml` propio de este servicio**: no se creó — se asume que la Postgres y el
  cluster de Pulsar los levanta la infraestructura común del proyecto (`implementacion/pulsar-infra/`
  para Pulsar; Postgres se puede compartir con el `docker-compose.yml` de DISP-03 apuntando a otra
  base de datos, o crear uno nuevo — decisión de equipo pendiente).
