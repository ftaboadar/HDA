# Resultados del experimento DISP-03

Hogar de los Alpes (HdA) — Entrega 3, MISO 2026-14
Disponibilidad de Verificación ante fallas de sistemas externos (Policía / RUES / Certificadora)

| | |
|---|---|
| **Ejecutado** | 2026-09-08 |
| **Proyecto GCP** | `hda-projectt` |
| **Región** | `southamerica-east1` (São Paulo) |
| **Entornos probados** | Local (docker-compose) y GCP real (Cloud Run + Pub/Sub + Cloud SQL) |
| **Casos de prueba** | CP-1..CP-7 (`plan.md`, sección 6) — 13 verificaciones mecánicas por entorno |

## Resumen

| Métrica | Valor |
|---|---|
| Local | **13/13** verificaciones mecánicas — 20/20 pruebas (7 integración + 13 unitarias de dominio) |
| GCP real | **11/13** verificaciones mecánicas — 5/7 casos de integración |
| Bugs reales encontrados y corregidos en GCP | **2** (ninguno visible en local) |
| RTT de red base (laptop → southamerica-east1) | **≈270 ms** |

## Qué se está validando

Hipótesis del experimento (`plan.md`, sección 3.2): si la Verificación de Proveedores encola cada
solicitud de forma asíncrona, reintenta con backoff acotado, y enruta a una DLQ tras agotar
reintentos, el resto del sistema sigue disponible aunque un verificador externo (Policía, RUES, o
la certificadora tipo CONTE) falle o se caiga — sin pérdida de datos y con trazabilidad completa.
Los 7 casos prueban eso mismo contra el **mismo código**, primero en local, después contra
infraestructura real en GCP.

## Local vs. GCP — las 13 verificaciones

| Caso | Métrica | Umbral | Local | ✓/✕ | GCP | ✓/✕ |
|---|---|---|---|---|---|---|
| CP-1 | disponibilidad_baseline | 1.0 | 1.0 | ✓ | 1.0 | ✓ |
| CP-2 | duración verificaciones rápidas | < 1.5s | 0.37s | ✓ | 8.61s | ✕ |
| CP-2 | certificadora lenta completa | true | true | ✓ | true | ✓ |
| CP-3 | trazabilidad_terminal | 1.0 | 1.0 | ✓ | 1.0 | ✓ |
| CP-3 | fallidas con motivo registrado | true | true | ✓ | true | ✓ |
| CP-4 | % fallidas en DLQ | true | true | ✓ | true | ✓ |
| CP-4 | % con motivo trazado | true | true | ✓ | true | ✓ |
| CP-4 | Policía no afectada | true | true | ✓ | true | ✓ |
| CP-4 | visibles en endpoint /dlq | true | true | ✓ | true | ✓ |
| CP-5 | % impacto por certificadora caída | 0.0 | 0.0 | ✓ | 0.0 | ✓ |
| CP-6 | % reprocesadas exitosas | 1.0 | 1.0 | ✓ | 1.0 | ✓ |
| CP-6 | duración del reproceso | < 60s | 0.39s | ✓ | 1.59s | ✓ |
| CP-7 | p95 latencia de aceptación | < 500ms | 39ms | ✓ | 536ms | ✕ |

Los otros 11 criterios dan idéntico resultado en ambos entornos. Los 2 que difieren son puramente de
latencia — el valor medido, no el mecanismo, es lo que cambia. Segunda corrida aislada de CP-2 en
GCP: 1.61s (vs. 8.61s en la corrida completa) — la variación 1.6s↔8.6s entre corridas es evidencia
directa de *cold start* bajo escalado a cero, que no aparece en local porque el worker de
docker-compose nunca se apaga.

## Lo que solo apareció al desplegar contra GCP real

Dos fallas genuinas encontradas en la primera pasada de `terraform apply` — ninguna visible en
local, ninguna hipotética. Encontradas, diagnosticadas y corregidas en el código/IaC (PR #3), no
parcheadas a mano.

### 1. Pub/Sub no podía invocar al worker — "request was not authenticated"

La suscripción push tenía el rol `roles/run.invoker` correcto sobre la service account invocadora,
pero al agente de servicio de Pub/Sub le faltaba permiso para **firmar** tokens OIDC como esa
cuenta — un segundo permiso, no documentado como obvio, que Google exige aparte del invoker.

```
WARNING The request was not authenticated. [...] The IAM principal lacks {run.routes.invoke} permission.
```

**Fix**: `google_service_account_iam_member` nuevo en `infra/iam.tf` —
`roles/iam.serviceAccountTokenCreator` para el agente de Pub/Sub sobre la SA invocadora.

### 2. Redelivery de Pub/Sub chocaba con el invariante del agregado

Pub/Sub es *at-least-once* — exactamente la amenaza a la validez que ya estaba anotada como teórica
en el README antes de desplegar. Confirmada en la práctica: una redelivery llegó después de que la
verificación ya estaba `COMPLETADA`, el agregado de dominio lanzó correctamente su invariante de
protección, pero el handler no lo capturaba — se propagaba como 500, y Pub/Sub reintentaba de nuevo.
Sin corregir, una verificación exitosa podía terminar mal enrutada a la DLQ.

```
app.domain.verificacion.verificacion.ErrorTransicionInvalida:
No se puede registrar un intento sobre una verificación en estado EstadoVerificacion.COMPLETADA
```

**Fix**: chequeo de idempotencia en `push_handler.py` — si la verificación ya está en estado
terminal, se responde 200 sin reprocesar.

## Veredicto

**H1 validada** — con una amenaza a la validez cuantificada, no una refutación.

- **En local**: los 13 criterios se cumplen. El mecanismo (desacople, reintentos con backoff, DLQ,
  reproceso, aislamiento) funciona exactamente como predice la hipótesis.
- **En GCP real**: el mecanismo se confirma funcionando de forma idéntica — DLQ, trazabilidad,
  aislamiento y reproceso pasan igual que en local (9/9 de esos criterios). Los 2 criterios que no
  cumplen son ambos de latencia geográfica, no de comportamiento: los umbrales (1.5s, 500ms) se
  calibraron contra loopback local, sin presupuesto para el RTT real de ≈270ms entre este equipo de
  desarrollo y São Paulo.

> **Caveat sobre el caveat**: ese RTT mide laptop-de-desarrollador → región, no
> usuario-final-LATAM → región. Un despliegue real serviría tráfico desde dentro de la misma región
> (o detrás de un CDN/edge), donde el presupuesto de red se parece más al local. Antes de aceptar
> 500ms/1.5s como el umbral de producción real, habría que remedir desde un cliente dentro de
> LATAM — este experimento no lo hizo.

## Infraestructura desplegada (real)

| Recurso | Nombre | URL / identificador |
|---|---|---|
| Cloud Run | disp03-poc-api | `disp03-poc-api-lpkhgnidhq-rj.a.run.app` |
| Cloud Run | disp03-poc-worker | `disp03-poc-worker-lpkhgnidhq-rj.a.run.app` |
| Cloud Run ×3 | disp03-poc-mock-{policia,rues,certificadora} | `*.a.run.app` |
| Cloud SQL | disp03-poc-verificacion | `hda-projectt:southamerica-east1:disp03-poc-verificacion` |
| Pub/Sub | verificacion-solicitudes / -fallidas | + suscripciones push/pull |
| Artifact Registry | disp03-poc-hda | `southamerica-east1-docker.pkg.dev` |

Para destruir: `cd infra && terraform destroy -var=project_id=hda-projectt -var=region=southamerica-east1`

## Referencias

- Plan del experimento: `experimento-arquitectura/implementacion/DISP-03/plan.md`
- Casos de prueba (implementación): `experimento-arquitectura/implementacion/DISP-03/tests/test_escenarios_disp03.py`
- Datos crudos: `experimento-arquitectura/implementacion/DISP-03/tests/results/resultados_disp03.jsonl`
- Fix de los 2 bugs de GCP: PR #3, `fix/gcp-pubsub-iam-e-idempotencia`
- Reporte visual: https://claude.ai/code/artifact/bb9ff636-2ae1-4384-b1a1-7fd26ac35b89
