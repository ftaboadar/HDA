# Hogar de los Alpes — Entrega 3: Diseño de Experimentación

Proyecto de curso **Hogar de los Alpes (HdA)**, MISO 2026-14 (Maestría en Ingeniería de Software).
Este README documenta el **ejercicio de experimentación de arquitectura DISP-03**, la entrega en
curso del proyecto.

> Para orientación de estructura de repo, reglas de la rúbrica y roles de equipo, ver
> [`AGENTS.md`](AGENTS.md) — es el punto de entrada agnóstico de herramienta (Claude Code, Gemini
> CLI, Codex CLI). Este README se enfoca en el contenido del ejercicio, no en cómo trabajar en el repo.

## El ejercicio: DISP-03 — Verificación de Proveedores ante falla de certificadora externa

### Escenario de calidad bajo prueba (tabla ATAM)

| Campo | Contenido |
|---|---|
| **Fuente** | Entidad certificadora externa (tipo CONTE) — responde en 24–48h, a diferencia de Policía Nacional y RUES/Cámara de Comercio, que responden en línea |
| **Estímulo** | El sistema externo de verificación no responde, falla o excede su SLA durante el registro, aprobación o re-validación de un proveedor |
| **Artefacto** | Verificación (submódulo de Proveedores) + Bus de Eventos / Dead Letter Queue |
| **Ambiente** | Operación 24/7, fase de verificación/re-validación de proveedores |
| **Respuesta** | La verificación pendiente queda en espera sin bloquear al resto de la cola; tras agotar reintentos, el evento se enruta a la DLQ para revisión manual, sin detener la coreografía global |
| **Medida de la respuesta** | Disponibilidad del proceso de verificación ≥ 99.9%; 100% de las verificaciones fallidas quedan trazables en la DLQ y reprocesables en < 24h |

### Hipótesis

- **H1 (trabajo):** encolar cada solicitud de verificación de forma asíncrona, aplicar reintentos con
  backoff exponencial acotado, y enrutar a una DLQ tras agotar reintentos, permite que el resto de
  solicitudes (dirigidas a otros proveedores u otro sistema externo) sigan procesándose sin
  degradación medible, cumpliendo ambas medidas de respuesta de DISP-03.
- **H0 (nula):** sin ese desacople, la caída o degradación de un solo sistema externo certificador
  degrada o bloquea la disponibilidad del proceso completo de Verificación.

### Tácticas arquitectónicas bajo prueba

Desacople productor/consumidor (cola asíncrona) · Timeout · Reintento con backoff exponencial +
jitter · Dead Letter Queue · Reproceso manual/asistido · Aislamiento por partición/routing key.

### Casos de prueba implementados (CP-1..CP-7)

Los 7 casos corren contra el stack real (Docker: API + worker + RabbitMQ + Postgres + 3 mocks de
sistemas externos), no simulados en memoria. Mecánica común de cada caso:

1. Inyecta la falla en el mock correspondiente vía `POST /_control/config`
   (`modo: ok|error_parcial|caido`, `latencia_ms`, `tasa_error`).
2. Dispara carga con `POST /verificaciones {proveedor_id, tipo_verificador}`.
3. Espera estado terminal (`COMPLETADA` / `FALLIDA_DLQ`) por polling sobre `GET /verificaciones/{id}`.
4. Mide y registra la métrica del caso.
5. Verifica un umbral con `assert` de pytest (verificación mecánica, no el veredicto de hipótesis).

| # | Escenario | Estímulo inyectado | Resultado esperado | Métrica registrada | Umbral real (código) |
|---|---|---|---|---|---|
| CP-1 | Baseline, todo disponible | 9 verificaciones mixtas (policía/rues/certificadora), mocks en `ok` | Todas completan, 0 en DLQ | `disponibilidad_baseline` | `== 1.0` |
| CP-2 | Certificadora lenta (dentro de SLA) | Certificadora `ok`, `latencia_ms=2000`; 5 de policía en paralelo | Policía no espera a la lenta; la lenta igual completa | `duracion_verificaciones_rapidas_s`, `certificadora_lenta_completa` | `< 1.5s`; `COMPLETADA` |
| CP-3 | Errores intermitentes | 20 verificaciones certificadora, `error_parcial`, `tasa_error=0.5` | 100% llega a estado terminal; fallidas con motivo | `trazabilidad_terminal`, `fallidas_con_motivo_registrado` | `== 1.0`; `True` |
| CP-4 | Caída dura y sostenida | 8 certificadora + 5 policía; certificadora `caido` | 8 a DLQ con motivo y visibles en `/dlq`; policía no afectada | `pct_fallidas_en_dlq`, `pct_con_motivo_trazado`, `policia_no_afectada`, `visibles_en_endpoint_dlq` | los 4 `True` |
| CP-5 | Aislamiento | 10 verificaciones policía/rues; certificadora `caido` | 0% de impacto | `pct_impacto_por_certificadora_caida` | `== 0.0` |
| CP-6 | Recuperación + reproceso | 6 caen a DLQ → certificadora `ok` → `POST /dlq/{id}/reprocesar` | 100% reprocesadas completan, dentro de ventana comprimida | `pct_reprocesadas_exitosas`, `duracion_reproceso_s` | `== 1.0`; `< 60s` |
| CP-7 | Carga concurrente + falla a mitad | 15 + 15 certificadora, cae a mitad | Latencia de aceptación de la API estable (no la de procesamiento) | `p95_latencia_aceptacion_ms` | `< 500ms` |

**Nota de escala — por qué el umbral real no es literal "99.9%":** con los volúmenes de un PoC
(N=8..30), un porcentaje como 99.9% no es estadísticamente significativo. Los asserts traducen la
medida de respuesta de DISP-03 a invariantes exactas y alcanzables a esta escala (ej. "0
verificaciones perdidas", "100% terminan en un estado terminal") en vez del porcentaje literal. La
generalización de esa invariante al 99.9% real es una amenaza a la validez que corresponde señalar
al validar la hipótesis, no algo que el PoC resuelva por sí mismo.

### Resultado de la Regla 5 (DDD, 45pt de la rúbrica)

Implementada sobre el mismo servicio de Verificación: agregado `Verificacion` con invariantes
protegidos, arquitectura hexagonal con 2 puertos (repositorio + verificación externa), persistencia
real (Postgres/Cloud SQL vía SQLAlchemy), eventos de dominio intra-servicio con dispatcher, y CQS
(comandos vs. queries separados). Detalle completo y evidencia por criterio en
[`experimento-arquitectura/implementacion/DISP-03/README.md`](experimento-arquitectura/implementacion/DISP-03/README.md).

### Dónde está todo

- **Diseño completo del experimento** (contexto de negocio, arquitectura del PoC, variables,
  compresión de escala temporal, criterios de éxito/fracaso, amenazas a la validez):
  [`experimento-arquitectura/implementacion/DISP-03/plan.md`](experimento-arquitectura/implementacion/DISP-03/plan.md)
- **Documentación operativa del código** (estructura, cómo correr local/GCP, evidencia de la Regla 5):
  [`experimento-arquitectura/implementacion/DISP-03/README.md`](experimento-arquitectura/implementacion/DISP-03/README.md)
- **Código de los casos de prueba**:
  [`experimento-arquitectura/implementacion/DISP-03/tests/test_escenarios_disp03.py`](experimento-arquitectura/implementacion/DISP-03/tests/test_escenarios_disp03.py)
- **Los 9 escenarios de calidad del proyecto** (DISP-03 es uno de 3 de Disponibilidad):
  [`experimento-arquitectura/contexto/escenarios_calidad.md`](experimento-arquitectura/contexto/escenarios_calidad.md)

### Correr el experimento localmente

```bash
cd experimento-arquitectura/implementacion/DISP-03
make local-run          # docker compose up + espera salud + pytest + reporte
```

RabbitMQ management UI: `http://localhost:15672` (hda/hda). API: `http://localhost:8000/docs`.
