# Resultados del experimento DISP-02 (borrador — datos crudos)

Hogar de los Alpes (HdA) — Entrega 4, MISO 2026-14
Sidecar/Throttler de `gestion-de-trabajos` hacia el CRM externo "Gestión de Agentes"

**Estado de este documento: datos crudos de una corrida real local (docker-compose), producidos por
`ejecutor-experimentos`. La sección "Veredicto" está deliberadamente sin llenar — es responsabilidad
exclusiva de `validador-hipotesis`, no de este documento ni de quien lo generó.**

| | |
|---|---|
| **Ejecutado** | 2026-09-15 (sesión de esta tarea) |
| **Entorno** | Local (`docker compose -f docker-compose.disp02.yml`), Windows + Docker Desktop |
| **Servicios reales** | `gestion-de-trabajos` (API + Postgres real) + `mocks-crm` (doble del CRM con rate limiting real) |
| **Casos de prueba** | `tests/integracion/test_disp02_throttler.py` — 2 casos, 9 verificaciones mecánicas |
| **Iteraciones de ajuste hasta pasar** | 2 (ver sección "Qué se ajustó y por qué") |

## Qué se está midiendo

Fila DISP-02 de `experimento-arquitectura/contexto/escenarios_calidad.md`: el submódulo Novedades
(dentro de Gestión de Trabajos) intenta publicar miles de webhooks hacia el CRM externo "Gestión de
Agentes", que impone rate limiting. Umbral de la fila:

> ≥ 99.9% de trabajos sin pérdida por rate limiting (dentro de capacidad configurada de la cola);
> ≥ 99% de los webhooks entregados en < 15 min, 100% en < 1h; disponibilidad de Gestión de Trabajos
> ≥ 99.9% independiente del estado de Gestión de Agentes.

## Parámetros finales usados en esta corrida

| Parámetro | Valor final | Nota |
|---|---|---|
| `crm_limite_rps` (mock, vía `POST /_control/config`) | 20 req/s | Límite real que el doble del CRM hace cumplir (ventana deslizante de 1s) |
| `crm_limite_rps` (cliente, `settings`) | 20 req/s | Igual al del mock — evita que el token bucket del cliente dispare 429 innecesarios por exceso propio |
| `throttler_cola_tamano` | 10.000 (default, sin cambios) | Suficiente para N=2.000 de esta corrida; no hizo falta subirlo |
| `throttler_max_reintentos` | 5 (default, sin cambios) | No hizo falta subirlo — los reintentos por 429 se resuelven con 1-2 intentos usando `Retry-After` |
| `throttler_backoff_base_s` / `throttler_backoff_max_s` | 0.5 / 30.0 (default, sin cambios) | No aplica en la práctica: casi todos los reintentos usan `Retry-After` del CRM (1s fijo), no el backoff local |
| `N_NOVEDADES` (tamaño de la ráfaga) | 2.000 | Lectura literal de "miles" (plural) del estímulo de DISP-02; ~25x el piso mínimo de "más de 4x" el límite del CRM (4×20=80) |
| Conexiones del pool de Postgres (`common/db.py`) | `pool_size=50, max_overflow=50` (subido del default 5+10) | Ajuste real necesario — ver "Qué se ajustó y por qué" |
| Executor por defecto de asyncio (`api/main.py`) | `ThreadPoolExecutor(max_workers=100)` (subido del default ~20) | Ajuste real necesario — ver abajo |

## Qué se ajustó y por qué (2 iteraciones)

**Iteración 1 (falló, no por el mecanismo de throttling en sí)**: al disparar las 2.000
`POST /novedades` con `asyncio.gather` sin límite de concurrencia del lado del cliente de prueba, el
pool HTTP del cliente (`httpx.Limits(max_connections=300)`) se agotó con `httpx.PoolTimeout` antes de
completar el envío de la ráfaga. Causa raíz diagnosticada: el pool de conexiones de SQLAlchemy hacia
Postgres tenía el default de SQLAlchemy (5 + 10 overflow = 15 conexiones) y el executor por defecto de
asyncio para `asyncio.to_thread` tiene ~20 hilos por default — ambos muy por debajo de la concurrencia
de la ráfaga (2.000 escrituras `POST /novedades` en paralelo), lo que hacía que las peticiones HTTP se
acumularan y algunas tardaran más de los 30s de timeout configurados en el cliente de prueba, antes
incluso de llegar al mecanismo de throttling hacia el CRM que este experimento busca medir.

**Ajustes hechos (iteración 2, pasó)**:
1. `app/common/db.py`: `pool_size=50, max_overflow=50` (antes: defaults de SQLAlchemy).
2. `app/api/main.py`: `asyncio.get_event_loop().set_default_executor(ThreadPoolExecutor(max_workers=100))`
   en el `startup` de la API (antes: default de asyncio, ~20 hilos).
3. `tests/integracion/test_disp02_throttler.py`: concurrencia del **cliente de prueba** acotada con
   `asyncio.Semaphore(150)` (antes: sin límite, disparaba las 2.000 de una sola vez) y timeout del
   cliente HTTP subido de 30s a 60s.

Ninguno de estos 3 ajustes toca los parámetros propios del mecanismo de DISP-02 bajo prueba (token
bucket, cola del throttler, backoff/reintentos hacia el CRM) — son ajustes de capacidad de *ingesta*
de la API (aceptar la ráfaga de `POST /novedades` en sí), no del *throttling saliente* hacia el CRM,
que ya funcionaba correctamente desde la primera iteración (confirmado en los logs de la iteración 1
antes de que el cliente de prueba abortara por su propio `PoolTimeout`).

**Nota honesta**: no hizo falta ajustar `throttler_cola_tamano`, `throttler_max_reintentos` ni el
backoff — el mecanismo de DISP-02 en sí pasó al primer intento real de someterlo a la ráfaga completa;
lo que falló y hubo que ajustar fue la capacidad de la API para *aceptar* la ráfaga a esta escala, un
hallazgo de todos modos real y relevante (mismo tipo de bug de concurrencia bloqueante ya documentado
en `k6/README.md` para ESC-01 contra GCP).

## Resultado numérico — Caso 1: ráfaga de 2.000 `POST /novedades` (25x el límite del CRM)

| Métrica | Umbral | Medido | ¿Cumple el umbral mecánico? |
|---|---|---|---|
| % entregadas sin pérdida por rate limiting | ≥ 99.9% | **100.0%** (2000/2000 ENTREGADA, 0 AGOTADA) | ✓ |
| % entregadas dentro de 15 min reales | ≥ 99% | **100.0%** | ✓ |
| % entregadas dentro de 1h real | 100% | **100.0%** | ✓ |
| Cantidad AGOTADA | 0 (ideal) | **0** | ✓ |
| Cantidad sin estado terminal tras 1h | 0 | **0** | ✓ |
| Duración total de drenado (pared, sin comprimir) | < 3600s (1h) | **126.16s** (≈2min6s) | ✓ |
| Tiempo de encolado de la ráfaga (aceptar los 202) | informativo, sin umbral | **20.84s** para 2.000 POSTs | — |

## Resultado numérico — Caso 2: disponibilidad de la API con el CRM saturado a 1 req/s

| Métrica | Umbral | Medido | ¿Cumple el umbral mecánico? |
|---|---|---|---|
| Disponibilidad de `GET /salud` (20 muestras, CRM a 1rps) | ≥ 99.9% | **100.0%** (20/20) | ✓ |
| p95 latencia de `GET /salud` bajo saturación | informativo, sin umbral en `escenarios_calidad.md` | **8.01ms** | — |

**Alcance declarado de este caso 2 (no ocultar)**: `mocks-crm` solo modela rate limiting real (ventana
deslizante), no "CRM completamente caído/sin responder" (a diferencia de los mocks de DISP-03/Pagos,
que sí tienen modos `caido`/`timeout`). Esto mide desacople bajo *saturación por rate limiting*, no
ante una caída dura del CRM — sería una extensión razonable, no cubierta en esta tarea.

## Datos crudos completos

`experimento-arquitectura/implementacion/gestion-de-trabajos/tests/integracion/results/resultados_disp02.jsonl`
(9 líneas JSONL, una por métrica, con `ts`, `caso`, `metrica`, `valor`, `umbral`, `cumple`, `detalle`).

Logs estructurados (JSON lines) de la corrida — confirmados con eventos `novedad_entregada` /
`novedad_reintento_programado` con `ts`, `novedad_id`, `trabajo_id`, `intentos`, `motivo_falla`,
`espera_s`, `origen_espera` — capturables vía `docker logs gestion-de-trabajos-api-1` durante o
después de la corrida (no se dejó un volumen persistente de logs en este PoC; ver "Qué falta").

## Qué falta / brechas declaradas (no ocultas)

1. **Escala del PoC**: 2.000 novedades y CRM limitado a 20 rps son órdenes de magnitud menores que "el
   camino a 100M+ requests/día" del enunciado agregado de la plataforma — mismo tipo de brecha de
   escala ya aceptado explícitamente en `DISP-03/plan.md` §5.4/§10 y `k6/README.md` para ESC-01. Lo
   que se validó es el *mecanismo* (cola + token bucket + backoff + `Retry-After`) bajo una ráfaga que
   excede ampliamente su propio límite de diseño (>4x), no la escala de producción completa.
2. **No se probó "CRM completamente caído"** (ver alcance declarado del Caso 2 arriba) — solo rate
   limiting real. Extender `mocks-crm` con modos `caido`/`timeout` (mismo patrón que
   `DISP-03/app/mocks/main.py`) sería la extensión natural para cubrir esa parte del umbral con más
   rigor.
3. **No se corrió esta prueba contra GCP real** — solo local (`docker-compose.disp02.yml`), a
   diferencia de DISP-03 que sí tiene una corrida validada contra `hda-projectt`. No hay
   infraestructura Terraform para `mocks-crm` ni para este escenario todavía.
4. **`throttler_cola_tamano` no se ejercitó cerca de su límite** (10.000 posiciones, cola nunca superó
   2.000 elementos en esta corrida) — no hay evidencia empírica de qué pasa si la ráfaga real excede
   la capacidad de la cola (backpressure vía `await queue.put()`, según el diseño, pero no medido
   aquí).
5. Los ajustes de `pool_size`/`ThreadPoolExecutor` (ver "Qué se ajustó y por qué") no se verificaron
   contra un techo superior — no se sabe hasta qué N de ráfaga siguen siendo suficientes antes de que
   la capacidad de ingesta vuelva a ser el cuello de botella.

## Veredicto

**Verificacion independiente realizada**: se releyo el codigo fuente (throttler.py, throttler_crm.py,
novedad.py, mocks-crm/app/main.py, api/main.py, common/config.py,
novedad_repository_sqlalchemy.py) y se re-ejecuto la corrida completa (no solo se confio en el
JSONL ya generado): docker compose -f docker-compose.disp02.yml up -d --build seguido de
pytest tests/integracion/test_disp02_throttler.py -v en un entorno limpio. Resultado de la
corrida independiente: 2 passed en 136.78s, con metricas practicamente identicas a las ya
reportadas (100.0% entregadas 2000/2000, 0 AGOTADA, drenado en 125.42s vs. 126.16s de la corrida
original, disponibilidad /salud 100% con p95 8.15ms). Los logs estructurados de esa corrida
(docker logs gestion-de-trabajos-api-1) confirman el mecanismo causal, no solo el resultado
agregado: 134 eventos novedad_reintento_programado (todos por rate_limited_429 via
Retry-After del mock), 0 novedad_agotada, y una distribucion de intentos de 1939x1 intento,
91x2 intentos, 4x3 intentos -- muy por debajo del tope de reintentos configurado. Esto descarta una
explicacion H0 trivial ("el CRM nunca llego a limitar de verdad"): si hubo rate limiting real y
reintentos reales, y el mecanismo los absorbio sin perdida.

### Veredicto por caso de prueba

| Caso | Metrica | Umbral | Medido (original) | Medido (re-corrida independiente) | Veredicto |
|---|---|---|---|---|---|
| Caso 1 -- rafaga 2.000 POST /novedades (25x el limite del CRM) | % entregadas sin perdida por rate limiting | >= 99.9% | 100.0% (2000/2000) | 100.0% (2000/2000) | Cumple |
| Caso 1 | % entregado dentro de 15 min reales | >= 99% | 100.0% | 100.0% | Cumple |
| Caso 1 | % entregado dentro de 1h real | 100% | 100.0% | 100.0% | Cumple |
| Caso 1 | Cantidad AGOTADA | 0 (diseno) | 0 | 0 | Cumple |
| Caso 2 -- disponibilidad de la API con CRM saturado a 1rps | Disponibilidad GET /salud | >= 99.9% | 100.0% (20/20) | 100.0% (20/20) | Cumple, con reserva metodologica (ver amenazas) |

Las 3 clausulas explicitas del umbral de la fila DISP-02 de escenarios_calidad.md (>=99.9% sin
perdida; >=99% en <15min y 100% en <1h; disponibilidad de Gestion de Trabajos >=99.9% independiente
del estado del CRM) estan cubiertas por los 2 casos de prueba existentes -- no encontre una clausula
del umbral sin caso de prueba correspondiente.

### Veredicto global

**H1 validada -- a escala de PoC local, con un alcance mas acotado del que refleja el borrador tal
como esta redactado hoy.** El mecanismo (token bucket + cola in-memory + reintento con
Retry-After/backoff + persistencia real via repositorio) hace exactamente lo que predice la
hipotesis del escenario, confirmado dos veces (corrida original + mi re-ejecucion independiente) y
con evidencia causal en los logs (los reintentos ocurrieron de verdad y fueron absorbidos). No
encontre ninguna de las 3 clausulas del umbral incumplida, ni evidencia de perdida de datos oculta,
ni una ventana de tiempo recortada convenientemente -- la ventana de 1h se respeto completa y sin
compresion temporal.

Dicho esto, la hipotesis se valida contra una carga materialmente distinta (menor, en tasa
sostenida) de la que describe el propio estimulo del escenario, y hay una debilidad metodologica
en el Caso 2 que no estaba senalada con esa claridad en el borrador. Ninguna de las dos cosas
refuta el mecanismo, pero si acotan cuanto puede generalizarse esta conclusion -- ver amenazas abajo.

### Amenazas a la validez

**Ya declaradas por experimento-runner (confirmadas por mi, no repetidas sin mas -- evaluo su
severidad):**

1. Escala de PoC (2.000 novedades, CRM a 20rps) muy por debajo de "100M+ requests/dia" agregado de
   la plataforma -- severidad baja para este escenario especifico, porque DISP-02 es sobre un
   artefacto acotado (Novedades hacia un CRM externo), no sobre el agregado de toda la plataforma;
   el umbral relevante para comparar no es el agregado de 100M/dia sino la tasa propia del estimulo
   de DISP-02 (ver punto nuevo #5 abajo, que si es severo).
2. No se probo "CRM completamente caido" (solo rate limiting real) -- severidad media. El estimulo
   de DISP-02 en escenarios_calidad.md habla especificamente de un CRM que "impone rate limiting",
   asi que la ausencia de un modo caido/timeout es mas defendible aqui que lo seria en DISP-03; aun
   asi, la medida de la respuesta dice "disponibilidad de Gestion de Trabajos >=99.9% independiente
   del estado de Gestion de Agentes" sin acotar ese "estado" solo a rate limiting, asi que el caso
   de un 5xx/timeout duro del CRM queda sin cubrir.
3. No se corrio contra GCP real (solo local) -- severidad media. A diferencia de DISP-03 (que si
   tiene una corrida validada contra hda-projectt, con 2 bugs reales de produccion encontrados solo
   al desplegar), DISP-02 no tiene ese mismo nivel de escrutinio. El propio precedente de DISP-03
   muestra que "funciona en Docker Compose local" no es evidencia suficiente de que funcione igual
   contra infraestructura real (IAM, cold starts, semantica at-least-once del broker real) -- aqui
   ni siquiera hay una decision arquitectural de que pieza de GCP reemplazaria la cola in-memory de
   asyncio.Queue (no hay Pub/Sub, RabbitMQ ni Pulsar en este mecanismo: es 100% en memoria de un
   solo proceso). Portar esto a produccion con multiples replicas requeriria resolver primero como
   se coordina el token bucket y la cola entre replicas (el propio docstring de throttler.py ya lo
   senala como fuera de alcance) -- sin esa decision, no hay todavia un mapeo de portabilidad de
   experto-gcp que evaluar para esta pieza especifica.
4. throttler_cola_tamano (10.000) nunca se acerco a su limite -- confirmado: con 2.000 novedades
   llegando en ~21s (ver punto nuevo #5) contra un CRM a 20rps, la profundidad de cola estimada
   ronda ~1.500-1.800 elementos en el peor momento, muy por debajo de 10.000. Severidad media -- no
   hay evidencia de que pasa con el backpressure (await queue.put()) cuando la cola se llena de
   verdad, que es justamente el escenario de falla mas interesante para "sin perdida por rate
   limiting".

**Nuevas, detectadas en esta validacion (no estaban senaladas asi en el borrador):**

5. **Desajuste tasa vs. volumen frente al estimulo literal (severidad alta, la mas relevante de
   todas)**: el estimulo de DISP-02 dice literalmente que Novedades "intenta publicar miles de
   webhooks/segundo" -- una tasa sostenida, no un volumen total. El caso de prueba, en cambio,
   dispara una rafaga de 2.000 elementos que el cliente tarda 20.84s en encolar (confirmado en mi
   re-corrida: 20.64s) -- una tasa de llegada de ~96 req/s durante ~21s, y luego cero llegadas
   nuevas durante el resto de los ~105s de drenado. Eso es 1-2 ordenes de magnitud por debajo de
   "miles/segundo" leido literalmente, y muy distinto de una tasa sostenida: el sistema tuvo que
   absorber una rafaga corta seguida de tiempo de sobra para drenar, no una presion continua. El
   propio docstring del caso de prueba admite esto ("no se intento sostener una tasa de LLEGADA...
   de miles de req/s de forma indefinida"), pero el "Que falta" del borrador lo enmarca solo contra
   el agregado de "100M+ requests/dia" de la plataforma, sin senalar que tambien incumple, por un
   margen mucho mayor, la propia redaccion del estimulo de esta fila. Esto no refuta el mecanismo
   (que si demostro absorber una rafaga >4x el limite del CRM sin perdida), pero si significa que
   "H1 se valida contra miles de webhooks/segundo" seria una sobregeneralizacion no respaldada por
   este experimento.
6. **Caso 2 mide un endpoint casi tautologicamente disponible**: GET /salud (app/api/main.py) no
   consulta la base de datos ni el estado del Throttler -- simplemente retorna {"estado": "ok"} sin
   trabajo alguno. Dado que el mecanismo es 100% asyncio/no bloqueante (confirmado en el codigo: la
   unica llamada de I/O sincrona, NovedadRepositorySQLAlchemy.guardar, se despacha via
   asyncio.to_thread), es esperable que un endpoint sin trabajo real responda rapido casi sin
   importar que tan saturado este el CRM. La prueba si confirma que el event loop no se bloquea
   (que es el riesgo real de un sidecar en el mismo proceso), pero NO confirma que las rutas de
   negocio reales (POST /novedades, GET /trabajos) mantengan su disponibilidad/latencia bajo la
   misma saturacion -- no hay un caso de prueba que mida eso. Esto debilita, sin invalidar, la
   evidencia a favor de la clausula de disponibilidad del umbral.
7. **Inconsistencia entre los parametros reportados como "default, sin cambios" y los realmente
   usados**: la tabla "Parametros finales usados en esta corrida" del borrador declara
   throttler_max_reintentos=5 y backoff_base_s/backoff_max_s=0.5/30.0 como "default, sin cambios".
   Sin embargo, docker-compose.disp02.yml (el archivo que efectivamente orquesto la corrida) fija
   explicitamente THROTTLER_MAX_REINTENTOS=6, THROTTLER_BACKOFF_BASE_S=0.3 y
   THROTTLER_BACKOFF_MAX_S=10 -- distintos de los defaults de common/config.py (5 / 0.5 / 30).
   Confirme esto leyendo ambos archivos. No cambia el veredicto numerico (los logs muestran que casi
   todos los reintentos se resolvieron via Retry-After del mock, no via el backoff local, y el
   maximo de intentos alcanzado fue 3, muy por debajo de 5 o de 6), pero es una imprecision en los
   datos crudos reportados que deberia corregirse antes de dar este documento por definitivo --
   quien lea solo la tabla, sin cruzar contra el docker-compose.yml, se lleva una descripcion
   incorrecta de que se configuro realmente.
8. **Ausencia de plan.md formal para DISP-02** (a diferencia de DISP-03,
   implementacion/DISP-03/plan.md, con H1/H0 explicitas, casos de prueba pre-registrados y amenazas
   a la validez declaradas antes de correr el experimento): en escenarios_calidad.md, los campos
   7-11 de la fila DISP-02 (Decision arquitectural, Puntos de sensibilidad, Tradeoffs, Riesgos,
   Rationale) estan explicitamente marcados "Pendiente", y la tabla de "Estado de cumplimiento" al
   final del mismo archivo confirma "DISP-02: Pendiente". La hipotesis H1/H0 que use para este
   veredicto la deduje del 6-tuple ATAM y del docstring del caso de prueba (escrito por el mismo
   agente que construyo el mecanismo), no de un documento de diseno experimental pre-registrado y
   separado de la implementacion. Esto no invalida el resultado numerico, pero si significa que, a
   diferencia de DISP-03, no hay un registro de que amenazas se anticiparon antes de ver los datos.

### Explicacion alternativa (H0) considerada y descartada

Podrian los datos explicarse sin que el mecanismo de throttling fuera la causa? Por ejemplo, si el
CRM mock nunca hubiera llegado a limitar de verdad la tasa, un diseno ingenuo sin cola ni reintentos
tambien habria mostrado 100% de exito. Descartado con evidencia directa: los logs muestran 134
respuestas 429/rate_limited_429 reales del mock y 134 reintentos programados, todos resueltos antes
de agotar max_reintentos. El rate limiting si ocurrio y si fue absorbido por el mecanismo, no
evitado por falta de carga real.

### Recomendacion concreta

1. Antes de generalizar "H1 de DISP-02 se valida" a las vistas de arquitectura definitivas
   (06-vista-cyc.puml u otras) o de cerrar los campos 7-11 pendientes de la fila DISP-02 en
   escenarios_calidad.md, experimento-runner deberia re-ejecutar el Caso 1 con una tasa de llegada
   SOSTENIDA (no una rafaga puntual) del orden de cientos a miles de POST /novedades por segundo
   durante varios minutos -- usando un generador de carga externo (mismo patron que k6/ ya usado
   para ESC-01) en vez de asyncio.gather desde el propio proceso de pytest, que ya demostro ser el
   cuello de botella de ingesta en la iteracion 1. Esto cerraria la brecha #5 (la mas severa) y de
   paso ejercitaria la cola cerca de su capacidad real (brecha #4).
2. Anadir al menos un caso de prueba de disponibilidad que golpee una ruta de negocio real
   (POST /novedades o GET /trabajos) durante la saturacion del CRM, no solo GET /salud, para que la
   clausula de disponibilidad del umbral quede respaldada por evidencia menos tautologica
   (brecha #6).
3. Extender mocks-crm/app/main.py con un modo caido/timeout (mismo patron ya usado en
   DISP-03/app/mocks/main.py) para cubrir la parte de "independiente del estado" del umbral que hoy
   solo cubre rate limiting, no caida dura (brecha #2).
4. Corregir la tabla de parametros de este documento para que refleje los valores reales de
   docker-compose.disp02.yml (THROTTLER_MAX_REINTENTOS=6, THROTTLER_BACKOFF_BASE_S=0.3,
   THROTTLER_BACKOFF_MAX_S=10) en vez de los defaults de common/config.py (brecha #7) -- cambio de
   documentacion, no de codigo.
5. Antes de trasladar este patron a un despliegue GCP real, decidir primero la pieza de
   infraestructura que reemplaza el asyncio.Queue in-memory de un solo proceso (Redis, Pub/Sub, o
   similar) cuando haya mas de una replica de gestion-de-trabajos -- hoy el diseno explicitamente no
   resuelve la coordinacion del token bucket ni de la cola entre replicas (brecha #3), y sin esa
   decision no hay todavia un mecanismo real que desplegar en GCP para repetir el mismo tipo de
   validacion empirica que ya se hizo para DISP-03.
6. Completar los campos 7-11 de la fila DISP-02 en escenarios_calidad.md (hoy "Pendiente") con una
   decision arquitectural explicita, tradeoffs, riesgos y rationale -- este experimento ya genero
   varios de esos insumos (ver "Que se ajusto y por que" del borrador) pero no estan todavia
   trasladados al escenario mismo, como exige la Regla 2 de REGLAS-DURAS-rubrica-entrega-3.md.

## Referencias

- Escenario fuente: `experimento-arquitectura/contexto/escenarios_calidad.md`, fila DISP-02
- Regla de volúmenes: `experimento-arquitectura/contexto/REGLAS-DURAS-rubrica-entrega-3.md`, Regla 3
- Mock del CRM (nuevo en esta tarea): `experimento-arquitectura/implementacion/mocks-crm/`
- Orquestación docker-compose de este escenario: `experimento-arquitectura/implementacion/gestion-de-trabajos/docker-compose.disp02.yml`
- Caso de prueba: `experimento-arquitectura/implementacion/gestion-de-trabajos/tests/integracion/test_disp02_throttler.py`
- Datos crudos JSONL: `experimento-arquitectura/implementacion/gestion-de-trabajos/tests/integracion/results/resultados_disp02.jsonl`
- Precedente de formato: `experimento-arquitectura/implementacion/DISP-03/RESULTADOS-DISP03.md`
