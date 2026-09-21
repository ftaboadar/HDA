# Guía paso a paso — Entrega 5 (de la primera línea de código a la sustentación)

**Para quién:** el equipo (Jhoan, Frans, Daniel). Qué se hace, en qué orden, con qué prompt para el agente y
cómo se verifica cada paso antes de seguir. El *qué* está en `15-arquitectura-entrega-5.md`, el *plan* en
`16-plan-entrega-5.md` y el *cómo* en `../implementacion/CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`.

**Regla para todos los prompts:** trabajar en la rama `feature/entrega-5-journey-saga` (o una rama que salga de
ella), un paso por sesión de agente, y no pasar al siguiente hasta que el punto de control esté en verde.

Encabezado común (pégalo al inicio de **cada** prompt):

```
Lee primero AGENTS.md, experimento-arquitectura/contexto/15-arquitectura-entrega-5.md,
experimento-arquitectura/contexto/16-plan-entrega-5.md y
experimento-arquitectura/implementacion/CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md.
Cumple la definición de terminado (CONVENCIONES §9). No inventes eventos, módulos ni endpoints que no estén en el
15: si falta algo, propónmelo primero. Al terminar: corre las pruebas, actualiza ESTADO-IMPLEMENTACION.md y
dame un resumen de qué quedó hecho y qué no. No hagas commit hasta que yo lo revise.
```

---

## Etapa 1 — Implementación (Jhoan, con agentes)

Orden obligatorio por dependencias: base común → coordinador de la saga (GT) → servicios que participan en la
saga → canales → BFF → journey local.

| # | Paso | Prompt (después del encabezado) | Punto de control |
|---|---|---|---|
| 1.1 | Base común (Fase 0, pasos 2-7) | *"Implementa la Fase 0 del plan, pasos 2 a 7: esquemas con JsonSchema del Schema Registry de Pulsar y publicador/consumidor genéricos con las propiedades de CONVENCIONES §3; compatibilidad BACKWARD y namespace hda/bff en el startup de la VM de Pulsar y en scripts/pulsar-namespaces-local.sh; AsyncAPI con todos los canales del catálogo §7 y §7.1; worker estándar con /salud; campos de observabilidad en logging_utils.py (§13); reglas de retrocompatibilidad, job oasdiff en el CI y prueba de arquitectura de imports (§14). Usa el subagente implementador-ddd para el código y experto-gcp para Pulsar y CI."* | `terraform validate` de los stacks, CI local (ruff + pytest) en verde, AsyncAPI válido |
| 1.2 | Gestión de Trabajos + **coordinador de saga + Saga Log** | *"Implementa Gestión de Trabajos según la Fase 1 del plan: layout por módulos (ciclo_vida, workflow, novedades, integraciones_externas), máquina de estados §6, coordinador de la Saga del Trabajo en workflow con los comandos de §7.1, plazos por paso, idempotencia, tablas saga_instancia y saga_log, sql/consultas-saga-log.sql, GET /sagas/{id}, POST /trabajos detrás de HABILITAR_ATAJO_CARGA, worker Pulsar. Las 21 pruebas actuales deben seguir pasando."* | Pruebas unitarias e integración en verde; una saga de prueba queda en `saga_log` |
| 1.3 | Proveedores (4 módulos + cola en Pulsar) | *"Implementa Proveedores según la Fase 1: módulos registro, verificacion (cola en Pulsar con DLQ nativa, A24; ampliar a técnicos y empresa), elegibilidad (A9, A10, A12), agenda (A14, reserva atómica); comandos PublicarElegibles, ReservarFranja y LiberarFranja; corrige el namespace de TOPIC_TRABAJOS_FINALIZADO; prefijo proveedores-poc. CP-1..CP-7 de DISP-03 deben seguir pasando."* | 17 unitarias + CP-1..CP-7 en verde; dos reservas simultáneas de la misma franja: solo una gana |
| 1.4 | Pagos | *"Implementa Pagos según la Fase 1: módulos liberacion_compensacion y pasarelas; comandos RetenerPago, LiberarPago y CompensarPago con sus eventos; estados RETENIDO → LIBERADO / COMPENSADO / FALLIDO; modo de falla en mocks-pagos para el caso de compensación. Las 19 pruebas actuales deben seguir pasando."* | Retener → liberar y retener → compensar probados; montos iguales |
| 1.5 | Reputación | *"Completa Reputación según la Fase 1: trabajos calificables, reputación compuesta A10, publicar ReputacionPublicada, consumir ScoringActualizado, worker desplegable."* | 9 pruebas actuales + las nuevas en verde |
| 1.6 | Marketplace | *"Crea el servicio Marketplace según la Fase 2 y la plantilla de CONVENCIONES §1: diagnóstico, cotización con franja, selección; publica SolicitudDiagnosticada y ProveedorSeleccionado; consume ElegiblesPublicados."* | Servicio en el CI y en los scripts; pruebas de contrato de sus eventos |
| 1.7 | Siniestros | *"Crea Siniestros: partner con ReglaDeAprobacion, red permitida y monto máximo; aprobar paso; SolicitarAprobacionNovedad → DecisionPartner; FacturarAPartner."* | Ídem |
| 1.8 | Suscripciones | *"Crea Suscripciones: contrato, ciclos, continuidad del proveedor A13, reserva recurrente A14; consume TrabajoFinalizado sin cambios en GT (MOD-03)."* | Ídem + diff vacío en `gestion-de-trabajos/` |
| 1.9 | Scoring | *"Crea Scoring: PerfilCrediticio desde TrabajoFinalizado, publica ScoringActualizado."* | Ídem |
| 1.10 | **BFF** | *"Crea el BFF REST según A25 y la Fase 2: rutas /v1 por actor (dueño, proveedor, partner, cliente de suscripción, operador), llamadas síncronas con timeout, X-Correlation-Id, consulta de sagas, OpenAPI en /docs y openapi.json exportado."* | `/docs` responde; oasdiff en verde |
| 1.11 | Journey local | *"Crea implementacion/journey/: docker-compose con los 9 servicios, Pulsar y los mocks, y la suite pytest que recorre JRN-01..05 por el BFF (§11.1 y §11.2). Crea la carpeta 'Journey E5' de Postman solo vía BFF, con el caso exitoso y el caso con compensación."* | Suite JRN-01..05 en verde; en `saga_log` hay sagas `COMPLETADA` y `COMPENSADA` |
| 1.12 | Auditoría de código | *"Usa el subagente rubrica-auditor para auditar el código contra REGLAS-DURAS-rubrica-entrega-5.md y el DDD de la Regla 5 de la Entrega 3. Solo reporta."* | Brechas corregidas o anotadas |

**Consolidar en la rama y abrir el PR** hacia `main` (lo organizan ustedes). El CI tiene que quedar en verde.

---

## Etapa 2 — Experimentos (Frans lidera; Daniel en MOD-02; Jhoan en ESC-01)

| # | Paso | Prompt | Punto de control |
|---|---|---|---|
| 2.1 | Hipótesis antes de medir | *"Con el subagente disenador-escenarios, escribe implementacion/journey/PLAN-EXPERIMENTOS.md para JRN-02 (ESC-01), JRN-03 (DISP-02) y JRN-04 (MOD-02): H1, H0, variables, casos, umbrales heredados de escenarios_calidad.md y amenazas a la validez, con el formato de proveedores/plan.md. Luego pide al subagente validador-hipotesis que lo revise antes de correr nada."* | Plan revisado |
| 2.2 | Despliegue en GCP | *"Con el subagente experto-gcp, corre PROJECT=<proyecto> implementacion/scripts/desplegar-todo.sh, registra cuánto tarda y actualiza ESTADO-IMPLEMENTACION.md §1 y §3 con las URLs y el Swagger de cada servicio."* | Los 9 `/salud` en 200; Newman "Journey E5" contra el BFF en verde |
| 2.3 | Observabilidad | *"Crea implementacion/QUERIES-GCP-JOURNEYS.md (§13) y prueba cada consulta contra el despliegue; crea el dashboard 'HdA E5' en observabilidad/ (servicios, journey por correlation_id, tipo_comunicacion, Saga Log por datasource Postgres, backlog de Pulsar)."* | Cada consulta devuelve datos; dashboard con los 9 servicios |
| 2.4 | Conexión al Saga Log | *"Escribe implementacion/gestion-de-trabajos/sql/README.md con la conexión a la Cloud SQL de GT por Cloud SQL Auth Proxy (DBeaver/psql) y pruébala con consultas-saga-log.sql."* | Consulta ejecutada desde el cliente |
| 2.5 | Correr JRN-02, JRN-03, JRN-04 (y JRN-01, JRN-05) | *"Con el subagente experimento-runner, corre los experimentos de PLAN-EXPERIMENTOS.md en GCP y guarda los datos crudos en implementacion/journey/resultados/. No des veredicto."* | Datos crudos guardados (k6, Newman, salidas SQL, capturas) |
| 2.6 | Veredicto | *"Con el subagente validador-hipotesis, evalúa los datos de implementacion/journey/resultados/ contra PLAN-EXPERIMENTOS.md y escribe el veredicto H1/H0 por escenario con sus amenazas a la validez."* | Veredicto por escenario |
| 2.7 | Apagar | *"Corre scripts/destruir-todo.sh y scripts/verificar-nada-facturando.sh y actualiza ESTADO §1."* | 0 recursos facturando |

---

## Etapa 3 — Documento, diagramas y refinamiento (Daniel lidera)

| # | Paso | Prompt | Punto de control |
|---|---|---|---|
| 3.1 | Refinar mapa de contextos y vistas | *"Agrega el BFF y el coordinador de sagas a 03-contextos-acotados-TO-BE.cml y a las 4 .puml; marca lo nuevo o cambiado en E5 con color y leyenda; escribe contexto/17-refinamiento-arquitectura.md con la tabla de cambios (qué cambió, por qué y qué resultado del experimento lo motivó)."* | Las `.puml` compilan con PlantUML; `cm validate` del `.cml` |
| 3.2 | Imágenes del equipo | A mano, con `diagramas/entrega-5/CORRECCIONES.md`: redibujar en Excalidraw/draw.io y exportar PNG/SVG | Todas las casillas marcadas |
| 3.3 | Documento final | *"Escribe el documento final de la Entrega 5 en contexto/19-documento-entrega-5.md: resultados cuantitativos y cualitativos y conclusiones por escenario (del veredicto), justificación de decisiones (§3.4), topología de datos y modelo de datos por servicio, tipos de mensajes (§7.2), esquemas y versionamiento (§7.3, §14), saga y Saga Log (§7.1, §11.2), DDD por servicio (capas, puertos y adaptadores, agregados), justificación de GCP, enlaces a AsyncAPI (HTML), Swagger de cada servicio, link del BFF y la colección Postman, y el refinamiento (17)."* | Revisado por los tres |
| 3.4 | Auditoría final | *"Con el subagente rubrica-auditor, audita el repo contra REGLAS-DURAS-rubrica-entrega-5.md ítem por ítem y ACLARACIONES-entrega-5.md. Solo reporta."* | Ningún ítem en cero |
| 3.5 | ACTIVIDADES y README | *"Actualiza ACTIVIDADES.md con lo que hizo cada integrante en la Entrega 5 y el README raíz con cómo levantar, probar y usar el sistema (link del BFF, Postman, runbook)."* | — |

---

## Etapa 4 — Video (los tres; cada uno graba su tramo)

Levantar el sistema con `RUNBOOK-SUSTENTACION.md` (al menos 40 min antes). Pestañas abiertas: Postman, Swagger del
BFF, DBeaver conectado al Saga Log, Logs Explorer, Grafana "HdA E5", `pulsar-admin` por SSH, editor con el código.

| # | Tramo | Quién | Qué se muestra | Min |
|---|---|---|---|---|
| 1 | Contexto y decisiones | Daniel | Negocio, 3 escenarios elegidos, vistas refinadas, por qué orquestación, BFF, JSON con esquema, topología | 3 |
| 2 | BFF | Jhoan | Swagger `/v1`, link, colección Postman, `X-Correlation-Id` | 2 |
| 3 | **Saga exitosa** | Frans | Postman: journey JRN-01 por el BFF; DBeaver: `consultas-saga-log.sql` paso a paso hasta `SAGA_COMPLETADA`; Logs Explorer por `correlation_id` (9 servicios, `tipo_comunicacion`, `bounded_context`, `modulo`) | 3 |
| 4 | **Saga con compensación** | Frans | Pasarela en modo falla → `PagoRetencionFallida` → `LiberarFranja` → `CANCELADO`; y la disputa → `CompensarPago`; Saga Log `SAGA_COMPENSADA` | 3 |
| 5 | ESC-01 | Jhoan | k6 al 4x por el BFF; Grafana p95 / req/s / backlog; comparación con el atajo; veredicto | 3 |
| 6 | DISP-02 | Frans | Ráfaga de novedades con CRM limitado; estados de novedades; reasignación en el Saga Log; veredicto | 3 |
| 7 | MOD-02 | Daniel | Trabajo en BR con MercadoPago; diff sin cambios en Colombia/Stripe/core; Strategy y Adapter en logs; veredicto | 3 |
| 8 | Eventos y esquemas | Daniel | Tipos de mensajes (§7.2); `pulsar-admin schemas get`; cambio incompatible rechazado; AsyncAPI en HTML | 2 |
| 9 | DDD en el código | Jhoan | Módulos, capas, puertos y adaptadores, un agregado con sus invariantes, comunicación entre módulos | 2 |
| 10 | Cierre | Todos | Conclusiones H1/H0 y qué se refinó por los resultados | 1 |

Después de grabar: `destruir-todo.sh` y `verificar-nada-facturando.sh`.

---

## Etapa 5 — Sustentación

1. Cada uno repasa **todo** el documento, no solo su parte (el tutor puede preguntarle a cualquiera). Preguntas a
   preparar: por qué orquestación y no coreografía; por qué JSON con esquema y no Avro o Protobuf; qué pasa si cae
   GT; cómo se compensa cada paso; por qué BD por servicio; dónde está cada concepto de DDD en el código.
2. Si el tutor pide demo: `RUNBOOK-SUSTENTACION.md` → link del BFF → Postman → Saga Log.
3. Al terminar: `destruir-todo.sh`.
