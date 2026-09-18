# Pagos

**Estado: esqueleto inicial (skeleton), extraído de `gestion-de-trabajos` a su propio
microservicio.** Este documento es honesto a propósito sobre qué falta — ver la sección "Qué
falta" al final. La lógica de dominio/aplicación NO se reescribió al separar este servicio: se
movió tal cual, solo se ajustó lo que exige la nueva frontera de proceso (ver más abajo).

## Qué es este servicio

Hasta esta separación, Pagos vivía como submódulo ACL dentro de `gestion-de-trabajos` (ver
`12-plan-entrega-4.md` sección 0.1: `Pagos` fue documentado como `GENERIC_SUBDOMAIN` externo, sin
`BoundedContext` propio en `03-contextos-acotados-TO-BE.cml`). El dueño del repo decidió, con
conocimiento de ese conflicto, reabrirlo y separar Pagos en un microservicio propio — con su
propia base de datos y despliegue. Este servicio:

1. Implementa el patrón **Strategy** (`ReglaRegional`: `ReglaColombia`, `ReglaBrasil`) para calcular
   comisión y validar montos/moneda según la región del trabajo que se está pagando.
2. Implementa el patrón **Adapter** (`IPasarelaDePago`: `PasarelaStripe`, `PasarelaMercadoPago`)
   para cobrar contra mocks HTTP de Stripe/MercadoPago (`implementacion/mocks-pagos/`).
3. Expone el agregado `Pago` (raíz de agregado propia — no existe en `07-vista-informacion.puml`,
   inconsistencia esperada dado que Pagos es un `GENERIC_SUBDOMAIN` comprado, no modelado a ese
   nivel de detalle).

## Frontera del API (decisión explícita de esta separación)

Antes de esta separación, `PagarTrabajo` dependía de `IRegistroTrabajosRepository`
(`application/ports/registro_trabajos.py`), poblado exclusivamente por
`application/dispatcher_eventos_dominio.py` de **Gestión de Trabajos** al reaccionar, dentro del
mismo proceso, al evento de DOMINIO `TrabajoFinalizado` — comunicación intra-servicio por eventos
(Regla 5, criterio 4), sin que `PagarTrabajo` tocara nunca el repositorio del agregado `Trabajo`.

Ahora que Pagos es un microservicio aparte, esa reacción automática entre procesos ya no es
posible sin infraestructura de integración adicional (cola/tópico consumido por este servicio) —
agregar eso está fuera del alcance de esta tarea de separación (que fue mover código, no diseñar
integración nueva). Por eso, `POST /pagos` recibe en el body los datos de
`RegistroTrabajoElegible` (`trabajo_id`, `proveedor_id`, `monto`, `moneda`, `region`) además de
`pasarela`, los guarda explícitamente vía `IRegistroTrabajosRepository.guardar()`, y luego llama a
`PagarTrabajo.ejecutar(trabajo_id, pasarela)` — la lógica INTERNA de `PagarTrabajo` no cambió en
absoluto: sigue sin conocer el agregado `Trabajo` ni su repositorio, y sigue dependiendo solo de
este puerto. Es el único cableado nuevo que exige la separación en dos procesos.

## Estructura (arquitectura hexagonal)

```
app/
  domain/               ← sin imports de FastAPI, SQLAlchemy ni httpx
    seedwork/           ← Entity, AggregateRoot, DomainEvent, ValueObject, IRepository
                           (copia propia, no importada de gestion-de-trabajos — cada BC es dueño
                           de su propio seedwork, deliberado no compartir código entre servicios)
    pagos/              ← agregado Pago, VOs propios (Dinero, Region, TrabajoId, ProveedorId,
                           PagoId, Pasarela, EstadoPago), repositorio (puerto), Strategy
                           ReglaRegional, fábrica, eventos de dominio
  application/
    ports/              ← IPasarelaDePago, IRegistroTrabajosRepository (interfaces que implementa
                           infrastructure/)
    commands/           ← PagarTrabajo, Compensar (mutan, retornan solo un id — CQS)
    queries/            ← ConsultarPago (solo lee)
    dispatcher_eventos_dominio.py  ← despachador en memoria de eventos de dominio de Pago
  infrastructure/
    persistence/        ← modelos SQLAlchemy (tablas `pagos`, `trabajos_elegibles_pago`) +
                           repositorios concretos
    adapters/            ← ReglaColombia/ReglaBrasil (Strategy), PasarelaStripe/PasarelaMercadoPago
                           (Adapter)
  common/                ← config (Pydantic Settings), db (engine/sesión SQLAlchemy), schemas
                           HTTP, logging
  api/main.py            ← FastAPI; solo llama a application/commands y application/queries
tests/unit/
  dominio/               ← pruebas de dominio puro, sin BD/HTTP
  aplicacion/            ← prueba de Compensar con fakes en memoria
```

Regla no negociable verificada: `domain/` no importa nada de `sqlalchemy`, `fastapi` ni `httpx`;
`application/` solo importa `domain/` y sus propios puertos; `api/main.py` no toca el ORM ni el
agregado directo, solo comandos/queries.

## Eventos: dominio vs. integración (distinción explícita, Regla 4)

- **Evento de DOMINIO**: `PagoMarcadoExitoso`, `PagoMarcadoFallido`, `PagoCompensado`
  (`domain/pagos/eventos.py`) — nacen dentro del agregado `Pago` en sus transiciones de estado,
  nunca cruzan el proceso por sí solos. `application/dispatcher_eventos_dominio.py` los recoge
  DESPUÉS de persistir el agregado y decide qué hacer con ellos.
- **Evento de INTEGRACIÓN**: este servicio NO tiene tópico de integración propio (no publica nada
  hacia otro microservicio) — los eventos de `Pago` solo se despachan y se loguean dentro de este
  proceso. Extensible sin tocar `pago.py` el día que algo deba reaccionar de verdad.
- **Comunicación entre módulos DEL MISMO servicio**: no aplica hoy — este servicio solo tiene un
  módulo (Pagos). Si se agregara otro módulo interno, debería comunicarse por eventos de dominio
  igual que exige la Regla 5 criterio 4, no por llamada directa.

## Cómo correrlo (local)

```bash
cd experimento-arquitectura/implementacion/pagos
python -m venv .venv && source .venv/Scripts/activate  # o .venv/bin/activate en Linux/Mac
pip install -r requirements.txt

export DATABASE_URL="postgresql+psycopg2://hda:hda@localhost:5435/hda_pagos"

uvicorn app.api.main:app --reload --port 8003
```

Requiere una Postgres real accesible en `DATABASE_URL` (crea las tablas `pagos`/
`trabajos_elegibles_pago` al arrancar, vía `Base.metadata.create_all()`). Para que `POST /pagos`
no falle al cobrar, se necesitan los mocks de Stripe/MercadoPago accesibles en
`STRIPE_MOCK_URL`/`MERCADOPAGO_MOCK_URL` (`implementacion/mocks-pagos/`).

O con Docker Compose (Postgres propio en el puerto host `5435`, API en `8003`):

```bash
docker compose up --build
```

## Endpoints

- `POST /pagos` — puebla `IRegistroTrabajosRepository` con los datos del trabajo (ver "Frontera
  del API" arriba) y ejecuta el comando `PagarTrabajo`. Body: `{trabajo_id, proveedor_id, monto,
  moneda, region, pasarela}` (`region`: `"CO"` o `"BR"`; `pasarela`: `"stripe"` o `"mercadopago"`).
  Retorna `{id}` (CQS: nunca el estado completo).
- `GET /pagos/{id}` — query `ConsultarPago`.
- `POST /pagos/{id}/compensar` — comando `Compensar`.
- `GET /salud`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/unit -v
```

`tests/unit/dominio/` no requiere BD ni HTTP — prueba `Pago` y `ReglaRegional` en aislamiento.
`tests/unit/aplicacion/` prueba `Compensar` con fakes en memoria. No hay todavía una prueba de
integración con Postgres real (ver "Qué falta").

## Los 5 criterios de la Regla 5 (`REGLAS-DURAS-rubrica-entrega-3.md`) — qué quedó cubierto

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Patrón de dominio | **Cubierto, con la misma brecha ya señalada en `gestion-de-trabajos`** | `domain/seedwork/` (Entity, AggregateRoot, DomainEvent, ValueObject, IRepository); agregado `Pago` como raíz clara; VOs propios (`Dinero`, `Region`, `TrabajoId`, `ProveedorId`, `PagoId`, `Pasarela`, `EstadoPago`); fábrica (`FabricaPago`); repositorio como puerto (`IPagoRepository`). **Pendiente heredado**: `ReglaRegional` como Strategy sigue siendo discutible como "servicio de dominio" en sentido estricto; no hay entidad hija real distinta de la raíz — no se corrigió en esta tarea de separación (fuera de alcance: mover código, no rediseñar el modelo de dominio) |
| 2 | Arquitectura hexagonal | **Cubierto** | `domain/` no importa sqlalchemy/fastapi/httpx; `application/` solo importa `domain/` y sus puertos; `api/main.py` solo llama comandos/queries. Verificado además por separación real de proceso: este servicio ni siquiera puede importar código de `gestion-de-trabajos` (no está en el mismo `sys.path` de despliegue) |
| 3 | Persistencia real | **Cubierto** | Postgres propia (`hda_pagos`) vía SQLAlchemy (`models_db.py`: tablas `pagos`, `trabajos_elegibles_pago`), repositorios concretos en `infrastructure/persistence/`. **Pendiente de verificar**: no se corrió una prueba de integración contra una Postgres real en esta sesión — ver pytest de `tests/unit` (fakes en memoria, no requieren Postgres) |
| 4 | Eventos de dominio intra-servicio | **Cubierto para lo que aplica dentro de este proceso** | `Pago` registra `PagoMarcadoExitoso`/`PagoMarcadoFallido`/`PagoCompensado` en sus transiciones; `application/dispatcher_eventos_dominio.py` los recoge DESPUÉS de persistir el agregado, nunca antes. Este servicio solo tiene un módulo de dominio (Pagos), así que no hay hoy una segunda reacción intra-servicio que demostrar — la que existía (poblar el registro de Pagos desde `TrabajoFinalizado`) era, precisamente, la reacción INTRA-servicio de `gestion-de-trabajos` antes de esta separación; ahora que Pagos es OTRO proceso, ese cableado pasó a ser explícito vía HTTP en `POST /pagos` (ver "Frontera del API"), no un evento de dominio cruzando procesos (eso sería un evento de integración, y agregarlo está fuera de esta tarea) |
| 5 | CQS | **Cubierto** | `PagarTrabajo`/`Compensar` retornan solo un `id`, nunca el agregado ni su estado de negocio; `ConsultarPago` solo lee, nunca muta — separación visible en carpetas `commands/` vs `queries/` |

## Qué falta (para quien complete este servicio)

- **Prueba de integración real** contra Postgres — no se hizo en esta sesión de separación (se
  priorizó mover el código sin romper los tests unitarios existentes).
- **Comunicación real entre Gestión de Trabajos y Pagos**: hoy `POST /pagos` requiere que el
  cliente HTTP aporte los datos del trabajo elegible en el body (ver "Frontera del API") — no hay
  ninguna cola/tópico que Pagos consuma para enterarse de un `TrabajoFinalizado` publicado por
  Gestión de Trabajos. Diseñar esa integración (probablemente vía el mismo tópico Pulsar
  `trabajos.finalizado` que ya existe, con Pagos como consumidor nuevo) es el siguiente paso
  natural y está fuera del alcance de esta tarea de separación.
- **Reversa real en la pasarela externa** al compensar: `Compensar` solo marca el estado de
  dominio; `IPasarelaDePago` solo define `cobrar()`, no `reversar()` (heredado de antes de la
  separación).
- **`07-vista-informacion.puml` no modela ninguna entidad `Pago`** — inconsistencia esperable dado
  que Pagos es `GENERIC_SUBDOMAIN` externo, heredada de antes de esta separación.
- **Migraciones formales (Alembic)**: no hay — `Base.metadata.create_all()` basta para este PoC.
