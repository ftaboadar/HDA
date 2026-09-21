# Reputación — Entrega 4 (Event Sourcing)

> **⚠ Revisado en Entrega 5 (2026-09-21).** En la Entrega 5 Reputación deja de solo auditar `trabajos.finalizado`: habilita la calificación del trabajo, publica `ReputacionPublicada` y consume `ScoringActualizado`; su consumidor se despliega como `worker` en Cloud Run. Ver [`../../contexto/15-arquitectura-entrega-5.md`](../../contexto/15-arquitectura-entrega-5.md) y [`../CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`](../CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md) §5.


Microservicio propio de Hogar de los Alpes, 4to servicio de la transacción larga (ver
`experimento-arquitectura/contexto/historico/12-plan-entrega-4.md`, secciones 1 y 6). Consume
`trabajos.finalizado` (evento de INTEGRACIÓN publicado por Gestión de Trabajos vía Apache Pulsar) y
expone el agregado `PerfilReputacion`, calificado por proveedor.

**Estado: esqueleto inicial construido en esta sesión, honesto sobre lo que falta -- ver sección
"Qué falta" al final.**

## Por qué Event Sourcing (y no CRUD clásico)

El plan de Entrega 4 (sección 6) ya justifica esta decisión a nivel de equipo: *"el read model
(Perfil de reputación) es una proyección acumulada de calificaciones -- el caso más natural de los
3"*. En términos concretos: el estado "actual" de `PerfilReputacion` (promedio, lista de
calificaciones) nunca se guarda directo -- se reconstruye reproduciendo la secuencia completa de
eventos `ProveedorCalificado` persistidos en la tabla `eventos_reputacion`. Si más adelante se
necesita auditar "¿cómo llegó este proveedor a 3.8 de promedio?" o recalcular el promedio con una
fórmula distinta (ej. ponderando por antigüedad), la respuesta está en el propio historial de
eventos -- no se perdió información al sobreescribir un campo `promedio` en una tabla mutable.

## Arquitectura hexagonal (Regla 5, criterio 2)

```
app/
  domain/               <- CERO imports de infraestructura
    seedwork/           <- ValueObject, DomainEvent, AggregateRootES (Event Sourcing)
    reputacion/
      value_objects.py  <- ProveedorId, TrabajoId, Garantia
      eventos.py         <- ProveedorCalificado (evento de DOMINIO)
      perfil_reputacion.py <- agregado raíz + entidad Calificacion + invariante de rango
      event_store.py     <- puerto IEventStore (interfaz, no SQLAlchemy)
  application/          <- casos de uso, CQS explícito
    commands/
      calificar_proveedor.py               <- MUTA (comando)
      registrar_evento_trabajo_finalizado.py <- MUTA, pero solo auditoría (ver más abajo)
    queries/
      consultar_perfil_reputacion.py       <- SOLO LEE (query)
    ports/
      registro_auditoria.py                <- puerto IRegistroAuditoria
  infrastructure/       <- adaptadores concretos
    persistence/
      models_db.py                    <- SQLAlchemy: EventoReputacionORM, TrabajoVistoORM
      event_store_sqlalchemy.py       <- implementa IEventStore
      registro_auditoria_sqlalchemy.py <- implementa IRegistroAuditoria
    messaging/
      consumidor_pulsar.py            <- consumidor pull de trabajos.finalizado
  api/main.py           <- FastAPI, no toca el ORM directo
```

`domain/` no importa `sqlalchemy`, `fastapi` ni `pulsar` -- verificable con:

```bash
grep -rE "^(from|import) (sqlalchemy|fastapi|pulsar)" app/domain/
# (sin resultados)
```

## Los dos tipos de evento -- explícito, no solo mencionado (Regla 4 de la rúbrica)

| Evento | Tipo | Dónde vive | Cruza a Pulsar? |
|---|---|---|---|
| `ProveedorCalificado` | **DOMINIO** | `domain/reputacion/eventos.py`, persistido en `eventos_reputacion` | Nunca. Es la fuente de verdad del agregado, no un mensaje de transporte. |
| `trabajos.finalizado` | **INTEGRACIÓN** | Publicado por Gestión de Trabajos, consumido en `infrastructure/messaging/consumidor_pulsar.py` | Sí -- es tráfico real de Pulsar que ENTRA a este proceso. |

El consumidor de `trabajos.finalizado` **nunca** convierte ese mensaje en un `DomainEvent` de este
módulo ni lo mete al Event Store de `PerfilReputacion` -- lo único que hace es invocar
`RegistrarEventoTrabajoFinalizado`, que escribe una fila de auditoría en `trabajos_vistos` (tabla
separada, sin relación con `eventos_reputacion`). Esto es deliberado y está documentado en el
docstring de ese comando: la guía del profesor (plan, sección 1.1) pide explícitamente que los
servicios puedan **oírse** sin **reaccionar ni completar la transacción** todavía -- eso es la Saga,
Entrega 5.

## CQS (Regla 5, criterio 5)

- **Comando** `CalificarProveedor.ejecutar(...)` -- muta estado, no devuelve para "consultar" sino
  como confirmación de lo que se acaba de escribir.
- **Comando** `RegistrarEventoTrabajoFinalizado.ejecutar(...)` -- muta estado (auditoría), sin
  relación con el agregado de negocio.
- **Query** `ConsultarPerfilReputacion.ejecutar(proveedor_id)` -- solo lee, nunca llama a
  `IEventStore.guardar_eventos`.

En `api/main.py` esto es visible directo en las rutas: `POST /calificaciones` instancia el comando,
`GET /reputacion/{id}` instancia la query -- nunca la misma clase para ambos casos.

## Decisión: proyección on-the-fly, no materializada

`ConsultarPerfilReputacion` reconstruye el agregado completo (`PerfilReputacion.desde_eventos(...)`)
en cada consulta, en vez de mantener una tabla `perfiles_reputacion` actualizada por un proyector
asíncrono. Para un PoC con pocos eventos por proveedor esto es la opción más simple de implementar
bien -- la alternativa (proyección materializada) es válida y probablemente necesaria si el volumen
de calificaciones por proveedor creciera mucho, pero construirla ahora sería anticipar una necesidad
de escala que ningún escenario de calidad de esta entrega exige todavía.

## Cómo correr localmente

```bash
cd experimento-arquitectura/implementacion/reputacion
docker-compose up -d postgres api
curl http://localhost:8001/salud
```

Para el consumidor de Pulsar (requiere el cluster de `../pulsar-infra` ya levantado):

```bash
docker-compose --profile consumidor up -d consumidor
```

Ejemplo de uso de la API:

```bash
curl -X POST http://localhost:8001/calificaciones \
  -H "Content-Type: application/json" \
  -d '{"proveedor_id": "prov-1", "trabajo_id": "trabajo-1", "puntaje": 5, "comentario": "Excelente"}'

curl http://localhost:8001/reputacion/prov-1
```

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest
```

9 pruebas de dominio puro (sin BD, sin Pulsar, sin FastAPI) en `tests/unit/dominio/`:

- Reconstrucción de `PerfilReputacion` desde una lista de eventos (`desde_eventos`).
- Aplicar un evento nuevo (`calificar()`) y verificar que queda pendiente de persistir.
- Invariante de dominio: puntaje fuera de `[1, 5]` lanza `PuntajeFueraDeRango`.
- Recalculo de promedio con múltiples calificaciones.
- Igualdad por valor de los Value Objects.

No se incluyó todavía una prueba de integración real contra Postgres (ver "Qué falta").

## Checklist Regla 5 (45pt, rúbrica de referencia adaptada a este servicio) -- estado explícito

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Patrón de dominio (entidades, VOs, seedwork, agregados, fábricas, repositorios como puertos) | **Cubierto** | `domain/seedwork/` (VO, DomainEvent, AggregateRootES), `domain/reputacion/` (agregado `PerfilReputacion`, entidad `Calificacion`, VOs, fábrica `crear()`, puerto `IEventStore`) |
| 2 | Arquitectura hexagonal (domain/application/infrastructure, dominio sin imports externos) | **Cubierto** | Ver árbol de carpetas arriba; verificado con `grep` que `domain/` no importa sqlalchemy/fastapi/pulsar |
| 3 | Persistencia real (motor real detrás de un repositorio/puerto) | **Cubierto en diseño, NO validado en ejecución real** | `EventStoreSQLAlchemy` sobre Postgres -- el `docker-compose.yml` de este servicio no se levantó de verdad en esta sesión (sin Docker disponible); el adaptador está escrito siguiendo el mismo patrón ya probado de DISP-03, pero falta correrlo contra una BD real |
| 4 | Eventos de dominio intra-servicio (distintos de integración) | **Cubierto, aunque con un solo módulo consumidor todavía** | `ProveedorCalificado` es el evento de dominio real (fuente de verdad del agregado); la distinción domino/integración está documentada explícita en este README y en los docstrings. A diferencia de DISP-03 (donde un evento de dominio dispara OTRO módulo interno, `ServicioDeElegibilidad`), aquí Reputación todavía no tiene un segundo módulo interno que reaccione a `ProveedorCalificado` -- es un candidato natural para una futura entrega si se necesita, ej. "recalcular NivelDeConfianza cuando el promedio cruza un umbral", pero no se inventa sin necesidad real (ver regla de comportamiento del rol) |
| 5 | CQS | **Cubierto** | Comandos y queries en carpetas separadas, visibles en `api/main.py` |

## Qué falta / qué queda pendiente (para quien retome esto)

- **No se ejecutó `docker-compose up` de verdad** en esta sesión (sin Docker disponible en el
  entorno donde se escribió el código) -- ni el Postgres de este servicio, ni el cluster de
  `pulsar-infra`, ni el consumidor contra un broker real. El código sigue el mismo patrón ya
  validado en DISP-03 (adaptador SQLAlchemy detrás de un puerto), pero **falta la validación de
  ejecución real** -- es el primer paso que debería dar quien continúe este servicio.
- No hay prueba de integración con Postgres real todavía (el rol pide "si el tiempo lo permite") --
  quedó priorizada la infraestructura del cluster de Pulsar (sección 1 del prompt de esta sesión)
  sobre esto.
- El consumidor de Pulsar (`consumidor_pulsar.py`) no se probó contra un broker real -- su lógica
  de parsing de payload asume que Gestión de Trabajos publica `{"trabajo_id": ..., "proveedor_id":
  ...}` como mínimo; si el schema real que define Frans (dueño de Gestión de Trabajos) trae otros
  nombres de campo, hay que ajustar `_procesar_mensaje()`.
- No se implementó ningún mecanismo de Dead Letter Policy nativo de Pulsar del lado del consumidor
  de este servicio (sí está mencionado como pendiente en el plan para Proveedores, sección 2.2) --
  por ahora el `negative_acknowledge` delega en la política default de la suscripción.
- El criterio 4 (eventos de dominio intra-servicio) está cubierto de forma más delgada que en
  DISP-03: aquí solo hay UN evento de dominio y un solo agregado -- no hay todavía un segundo módulo
  interno reaccionando a `ProveedorCalificado`. Si `rubrica-auditor` considera que esto no basta
  para el criterio (compararlo contra el ejemplo de DISP-03: `Verificacion` -> evento -> otro
  módulo, `ServicioDeElegibilidad`), un candidato natural sin inventar features de negocio sería:
  "cuando el promedio cruza cierto umbral, el módulo de scoring/alertas del propio servicio
  reacciona" -- pero eso NO se implementó aquí porque no hay ningún escenario de calidad ni
  necesidad de dominio ya modelada que lo exija todavía (ver `07-vista-informacion.puml`: no hay
  ningún otro módulo dentro de "Reputación y Calidad" mencionado ahí).
