# Reglas duras — Rúbrica Entrega 3 (Diseño de Experimentación)

Abstraído de `Entrega-003-DisenoExperimentacion.pdf` (MISO 2025-2, "Diseño Experimentación").
Estas reglas son **restricciones de cumplimiento obligatorio** para toda la Entrega 3 — no solo para
el experimento DISP-03 — y deben usarse como checklist de validación antes de dar cualquier
entregable de esta fase por terminado. Total: 100pt.

---

## Regla 1 — Cobertura: 9 escenarios, 3 por atributo (54pt)

- **MUST**: exactamente **3 escenarios de calidad por cada uno de los 3 atributos de calidad**
  definidos en la Entrega 2 (Modificabilidad, Escalabilidad, Disponibilidad/Elasticidad) → **9
  escenarios en total**.
- Puntaje: 6pt por escenario × 9 = 54pt. Un atributo con solo 2 escenarios completos pierde 6pt de
  forma directa, sin importar la calidad de los otros dos.
- **Estado actual**: `escenarios_calidad.md` ya contiene 9 escenarios (ESC-01/02/03, MOD-01/02/03,
  DISP-01/02/03) — cobertura cuantitativa cumplida. Ver Regla 2 para si cumplen el contenido mínimo.

## Regla 2 — Contenido mínimo obligatorio por escenario (no solo el 6-tuple ATAM clásico)

Cada uno de los 9 escenarios **MUST** incluir, como mínimo, los siguientes 11 campos — el 6-tuple
ATAM estándar **más 5 campos adicionales que la rúbrica exige explícitamente** y que no son parte
del formato ATAM clásico:

| # | Campo | ¿Ya está en `escenarios_calidad.md`? |
|---|---|---|
| 1 | Fuente | ✅ Sí |
| 2 | Estímulo | ✅ Sí |
| 3 | Artefacto | ✅ Sí |
| 4 | Ambiente | ✅ Sí |
| 5 | Respuesta | ✅ Sí |
| 6 | Medida de la respuesta | ✅ Sí |
| 7 | **Al menos una decisión arquitectural** (patrón y/o táctica) | ⚠️ Implícita en la columna "Artefacto"/"Respuesta" de algunos escenarios, pero no aislada como campo explícito por escenario |
| 8 | **Puntos de sensibilidad asociados** | ⚠️ Mencionados de forma dispersa (ver notas de pendientes #1 y #5), no como campo por escenario |
| 9 | **Tradeoffs** | ❌ No presente en el markdown actual |
| 10 | **Riesgos** | ❌ No presente en el markdown actual |
| 11 | **Rationale + pequeño diagrama** explicando la decisión de diseño | ❌ No presente por escenario (existen diagramas generales del proyecto, pero no uno específico por escenario) |

> **Implicación directa**: `escenarios_calidad.md`, tal como está hoy, **no alcanza el puntaje
> completo de la Regla 1** porque le faltan los campos 7–11 en los 9 escenarios. Esto es un gap de
> cumplimiento de rúbrica, no solo un "sería bueno tener". Cada uno de los 3 escenarios de cada
> atributo se califica de forma independiente (6pt c/u) usando "los criterios y templates descritos
> en el enunciado" — sin estos 5 campos, un escenario no está completo según la rúbrica.
- **Acción derivada**: antes de dar la Entrega 3 por completa, `escenarios_calidad.md` (o un
  documento derivado) debe extenderse para que **los 9 escenarios**, no solo DISP-03, tengan los 11
  campos. El experimento DISP-03 (`implementacion/DISP-03/plan.md`) ya cubre varios de estos campos
  en prosa (secciones 2.2, 4, 8, 10) pero deben quedar también como campos explícitos y trazables
  del escenario mismo, con el mismo formato que los otros 8.

## Regla 3 — Consistencia de volúmenes con el enunciado del proyecto

- **MUST**: la medida de la respuesta y el estímulo de cada escenario **deben reflejar los mismos
  volúmenes de transacciones (o mayores)** que los indicados en el enunciado del proyecto
  (`Proyecto-202614-HogarDeLosAlpes.pdf`) — no valores inventados o menores.
- Ejemplo textual de la rúbrica: si el atributo es escalabilidad, el escenario debe reflejar
  "igual o mayor capacidad de peticiones concurrentes a las indicadas en el enunciado".
- **Cifras de referencia del enunciado** (ya usadas en `escenarios_calidad.md` — deben mantenerse
  como piso, no reducirse en ninguna revisión futura):
  - +12.000 trabajos/día hoy → 36.000/día en 3 años (×3).
  - +45.000 proveedores registrados hoy → +100.000 en 3 años.
  - +25 millones de requests/día hoy, camino a 100M+.
  - Picos de hasta 4x el volumen en 48h por eventos climáticos.
  - Integraciones de siniestros de Seguros de los Alpes: crecimiento de 4–5x en peticiones diarias.
  - Entidad certificadora (relevante para DISP-03): SLA real documentado de 24–48h.
- **Chequeo específico para DISP-03**: el plan (`implementacion/DISP-03/plan.md`) ya referencia el
  SLA de 24–48h como el valor real a respetar en la simulación (con compresión temporal declarada
  explícitamente, sección 5.4) — esto es consistente con la regla. Cualquier caso de prueba futuro
  que reduzca artificialmente ese SLA sin declarar el factor de compresión violaría esta regla.

## Regla 4 — Comunicación explícita: microservicios basados en eventos

- **MUST**: todas las decisiones de diseño y arquitectura deben ceñirse a los fundamentos de una
  **arquitectura de microservicios basada en eventos**.
- **MUST**: cada escenario/decisión debe ser explícito sobre **qué tipo de medio de comunicación**
  usa — la rúbrica nombra literalmente: **eventos de dominio, eventos de integración, eventos
  "gordos" (fat events)**, entre otros. No basta con decir "usa eventos" de forma genérica.
- **Acción derivada**: en el experimento DISP-03 y en cualquier escenario nuevo, identificar
  explícitamente si el evento que cruza la cola/DLQ es un evento de **integración** (cruza el
  Bounded Context de Proveedores hacia fuera) o de **dominio** (interno al contexto), y si en algún
  punto se opta por un evento "gordo" (con todo el payload necesario para evitar consultas
  adicionales) vs. uno delgado (solo el identificador + tipo de evento). Esto hoy no está resuelto
  explícitamente en `implementacion/DISP-03/plan.md` y debe añadirse antes de implementar.

## Regla 5 — Implementación de un servicio con DDD + arquitectura basada en eventos (45pt)

- **MUST**: implementar **uno** de los servicios que se va a probar (no los 9 escenarios, un
  servicio concreto) cumpliendo los 5 criterios siguientes, cada uno con su propio puntaje (9pt c/u):

| # | Criterio obligatorio | Detalle mínimo exigido |
|---|---|---|
| 1 | **Patrón de dominio (DDD)** | Debe verse el uso de: entidades, objetos valor, *seedwork*, servicios de dominio, módulos, agregaciones, fábricas y repositorios |
| 2 | **Arquitectura hexagonal** | Puertos y adaptadores deben ser claros e identificables en el código/estructura del servicio |
| 3 | **Persistencia real** | El servicio debe usar un manejador de base de datos real para persistencia y consulta (no solo estructuras en memoria) |
| 4 | **Comunicación intra-servicio por eventos de dominio** | La comunicación **entre los módulos del propio servicio** debe hacerse por medio de eventos de dominio — no solo llamadas directas entre módulos |
| 5 | **Patrón CQS** | Debe quedar claro el uso separado de comandos vs. consultas/eventos (Command-Query Separation) en el servicio |

- **Implicación para DISP-03**: si el servicio elegido para esta implementación obligatoria es el de
  **Verificación de Proveedores** (candidato natural, dado que ya es el foco del experimento DISP-03
  en curso), su diseño interno en `implementacion/DISP-03/` deberá ampliarse más allá de lo
  planificado hasta ahora (que hoy describe una arquitectura de *integración* entre servicios vía
  RabbitMQ) para exhibir también: agregados/entidades/VOs del dominio Verificación, *seedwork*,
  repositorios, puertos/adaptadores hexagonales, persistencia real, eventos de dominio *internos*
  (distintos de los eventos de integración que ya cruzan a RabbitMQ), y separación explícita de
  comandos vs. consultas. **Esto todavía no está decidido ni planificado — es una decisión
  pendiente**, no una que este documento resuelva por sí solo.
- Nota: "uno de los servicios que usted desea probar" sugiere que el servicio implementado debe ser
  uno de los que aparecen como artefacto en alguno de los 9 escenarios — Verificación (DISP-03) es
  un candidato válido y coherente con el trabajo ya iniciado, pero la elección final es una decisión
  de equipo, no una regla impuesta por la rúbrica.

## Regla 6 — Presentación con template oficial (1pt)

- **MUST**: usar el **template de la entrega** provisto por el curso y seguir sus indicaciones.
- **Gap detectado**: el template de presentación de Entrega 3 **no está presente en la carpeta del
  proyecto** (`experimento-arquitectura/`) ni fue adjuntado junto con la rúbrica. Es un insumo
  pendiente de conseguir antes del cierre de esta entrega — sin él no se puede validar/cumplir esta
  regla, por bajo que sea su peso (1pt).

---

## Resumen de puntaje y riesgo de incumplimiento

| Bloque | Puntaje | Estado de cumplimiento hoy |
|---|---|---|
| 9 escenarios de calidad (Regla 1 + 2) | 54pt | ⚠️ Cobertura cuantitativa OK (9/9); **faltan campos 7–11 en los 9 escenarios** |
| Consistencia de volúmenes (Regla 3) | Transversal a las 54pt anteriores | ✅ Cumplido en las cifras usadas hasta ahora |
| Claridad de medios de comunicación por eventos (Regla 4) | Transversal a las 54pt | ⚠️ No se ha clasificado explícitamente evento de dominio / integración / gordo por escenario |
| Implementación de un servicio DDD + eventos (Regla 5) | 45pt | ⚠️ Existe una implementación de **integración/resiliencia** para Verificación (`implementacion/DISP-03/`: API, worker, colas, DLQ, reproceso — 7/7 pruebas pasan localmente), pero **todavía falta la capa DDD interna exigida** (entidades, VOs, seedwork, agregados, arquitectura hexagonal explícita, CQS) — ver `implementacion/DISP-03/README.md`, sección "Servicio DDD — todavía no implementado aquí" |
| Template de presentación (Regla 6) | 1pt | ❌ Template no disponible en el proyecto todavía |

**Mayor riesgo de puntos hoy**: los 45pt de la Regla 5 (implementación) son el bloque más grande y
el que no se ha empezado; y los 5 campos faltantes de la Regla 2 afectan a los 9 escenarios por
igual, no solo a DISP-03 — es un trabajo transversal a `escenarios_calidad.md` completo, no algo que
se resuelva únicamente dentro de la carpeta `implementacion/DISP-03/`.
