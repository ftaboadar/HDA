# Fixes sugeridos para PR #9 (feature/proveedores-pulsar-y-mocks)

Revisé el diff real del PR #9 contra `origin/main` (no un diff local por error, ya verificado
archivo por archivo con `gh pr diff 9`). Encontré 2 bugs de lógica reales en el código nuevo de
Pulsar, más un problema de higiene de repo. Todo lo de abajo lo armé yo, pero el patch se aplica
y se commitea con tu usuario — no toqué el PR ni el repo remoto.

## Cómo aplicar

```bash
git checkout feature/proveedores-pulsar-y-mocks
git apply 01-fixes-pulsar-dlq-y-gitattributes.patch
git add -A
git commit -m "fix: idempotencia en pulsar_consumer, backlog real en job_reproceso_dlq, .gitattributes"
git push
```

Si `git apply` se queja de contexto (por los CRLF, ver punto 3), probá con:
`git apply --ignore-whitespace 01-fixes-pulsar-dlq-y-gitattributes.patch`

## 1. `pulsar_consumer.py` — falta el chequeo de idempotencia contra redelivery

`push_handler.py` (Pub/Sub) ya tiene un chequeo explícito: si la verificación ya está en estado
terminal (COMPLETADA/FALLIDA_DLQ), ignora el mensaje en vez de reprocesarlo — porque Pub/Sub es
*at-least-once* y puede reentregar el mismo mensaje. Esto es la corrección al bug de producción
que ya está documentado en el README ("segunda vez... contra GCP real").

`pulsar_consumer.py` (nuevo en este PR) **no tiene ese mismo chequeo**. Pulsar también es
*at-least-once* — un ack lento bajo carga o un crash a mitad de proceso puede hacer que la
suscripción reentregue un mensaje ya resuelto. Sin el chequeo:

1. `RegistrarIntento` llama a `Verificacion.registrar_intento` sobre un agregado ya terminal.
2. El invariante del agregado lanza una excepción.
3. El `except` genérico de `_procesar_mensaje` la captura como "fallo no procesado" y hace
   `negative_acknowledge`.
4. Tras `max_redeliver_count` reintentos, el mensaje termina en la DLQ **nativa de
   infraestructura** (`TOPIC_SOLICITUDES_DLQ_NATIVO`) como si fuera una falla real — cuando en
   realidad era solo una redelivery duplicada de algo que ya se había completado bien.

**Fix aplicado**: agregué el mismo chequeo que ya existe en `push_handler.py` (`ConsultarVerificacion`
+ comparar contra `EstadoVerificacion.COMPLETADA` / `FALLIDA_DLQ`), justo antes de llamar a
`procesar_verificacion`. Si ya está terminal, se hace `acknowledge` directo y se loguea
`verificacion_redelivery_ignorada` (mismo nombre de evento conceptual que usa `push_handler.py`).

## 2. `job_reproceso_dlq.py` — el job de reproceso automático nunca se dispara

`obtener_backlog()` leía `resp.json().get("msgBacklog", 0)` del nivel raíz de la respuesta de
`GET /admin/v2/persistent/{tenant}/{namespace}/{topic}/stats`. Verificado contra la documentación
oficial de Pulsar (https://pulsar.apache.org/docs/2.10.x/admin-api-topics/): `msgBacklog` vive
**dentro de `subscriptions.<nombre>`**, no en el nivel raíz del JSON. Con esa lectura, la función
siempre devuelve `0` — el job nunca cruza el umbral y el reproceso automático de la sección 2.1 del
plan de Entrega 4 nunca se ejecuta contra un cluster real.

Además, ni siquiera arreglando la ruta del JSON funcionaría: `settings.pulsar_topic_fallidas` es un
tópico solo-productor (`PublicadorPulsar.__init__` solo hace `create_producer`, nunca `subscribe`),
así que no existe ninguna suscripción de la que leer `msgBacklog` en primer lugar.

**Fix aplicado**: en vez de depender de la API de Pulsar para este número, el job ahora mide el
backlog directamente contra Postgres con `ListarDLQ` (la query que YA existe y que el propio job ya
usaba para reprocesar) — es la fuente de verdad real de qué sigue en DLQ. Se eliminó la dependencia
de `httpx`/Admin REST para esto (dejé `httpx` intacto en el resto del proyecto, se sigue usando en
`worker/core.py` y en los adaptadores externos).

Verificado con `ruff check` + `ruff format --diff` sobre ambos archivos — pasan limpio.

## 3. Line endings CRLF en 77 archivos de `DISP-03`

Comparé `origin/main` vs. `origin/feature/proveedores-pulsar-y-mocks`: 77 de los archivos tocados
pasaron de LF a CRLF (probablemente un editor en Windows sin `core.autocrlf`/`.gitattributes`). Por
eso el diff de este PR en GitHub se ve enorme (cientos de miles de líneas) aunque el cambio lógico
neto es mucho más chico — casi todos los archivos aparecen "reescritos línea por línea" sin cambio
real de contenido, lo que hace casi imposible una revisión humana línea por línea en GitHub.

El patch agrega `.gitattributes` (`* text=auto eol=lf`) en la raíz del repo. Con eso puesto, después
de aplicar el patch conviene correr una sola vez:

```bash
git add --renormalize .
git commit -m "chore: normaliza line endings a LF"
```

Esto no lo incluí en el patch porque tocaría los 77 archivos con un diff gigante otra vez — mejor
que lo generes vos localmente después de aplicar `.gitattributes`, así el commit de normalización
queda separado y claramente identificado como tal.
