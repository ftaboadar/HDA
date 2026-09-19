# Actividades por miembro del equipo — Entrega Parcial
---

## Frans Taboada (`ftaboadar` en GitHub; identidades de git `frans` / `FRANS.TABOADA`)

- **Componentes a cargo:** Proveedores/DISP-03 (implementación DDD original, fixes de GCP/IAM/idempotencia), integración del plan de Entrega 4, separación de Pagos como microservicio, DISP-02 (throttler), validación de MOD-02, investigación y corrección iterativa de ESC-01 (10 corridas documentadas, causa raíz en cadena: sobresuscripción de conexiones → cold start → CPU de Cloud SQL → CPU de Cloud Run/GIL de Python).
- **Qué implementé (63 commits, el volumen más alto del equipo):**
  - Agregado `Verificacion` (DDD/hexagonal) y su ciclo de vida completo en Proveedores, con los 3 bugs reales de GCP corregidos vía `terraform plan` (`ca76f60`, `4a586c6`, `0a36054`).
  - Corrección de las métricas CP-2/CP-7 para medir el criterio real del plan, no un proxy (`ef391c5`, `180a32d`).
  - Separación de Pagos en microservicio independiente (`567604e`), construcción de DISP-02 (`09dd4e5`), validación documentada de MOD-02 (`ea895bd`).
  - Eliminación de ESC-02/ESC-03 al confirmarse fuera del alcance acordado (`c0d3fa0`).
  - Las 10 corridas de diagnóstico de ESC-01, cada una aislando y confirmando un cuello de botella distinto, hasta bajar el p95 de 14.2s a 5.2s (sin llegar aún al umbral de 2s) — documentado en detalle en `RESULTADOS-ESCALABILIDAD-GCP.md`.
  - Integró la mayoría de los Pull Requests del equipo a `main` (merges de los PRs #1-#5, #9-#15).
- **Cómo colaboré con el resto del equipo:** integró y mergeó el trabajo de Daniel (PR #7, Reputación + Pulsar infra) y de Jhoan (PR #9 y #16) hacia `main`. 

---

## Jhoan Felipe Sarmiento Ortiz

- **Componentes a cargo:** migración del publicador de Proveedores a Apache Pulsar, mocks externos (Policía/RUES/Certificadora), observabilidad (Grafana) y escenarios adicionales de GCP.
- **Qué implementé (2 commits, ambos PRs grandes integrados como squash — no es poco trabajo, es que cada uno representa un PR completo):**
  - `e90b7eb` "Feature/proveedores pulsar y mocks" (#9) — 207 archivos, +4771/-304 líneas: migró el publicador de Proveedores de RabbitMQ/Pub-Sub a Pulsar, aisló la latencia de aceptación con threadpool para SQLAlchemy, y ajustó el manejo asíncrono del push handler.
  - `0c13f0e` "Feature/gcp observabilidad y escenarios" (#16) — infraestructura de observabilidad (Grafana) y trabajo adicional de escenarios en GCP.
- **Cómo colaboré con el resto del equipo:** su trabajo en Proveedores es la base sobre la que Frans construyó el consumidor de `trabajos.finalizado` y el job de reproceso de DLQ.

---

## Daniel Felipe Urrego

- **Componentes a cargo:** microservicio Reputación (desde cero) e infraestructura inicial del cluster de Apache Pulsar.
- **Qué implementé (2 commits, PR #7 "reputacion-y-pulsar-infra"):**
  - `41801da` "Agregado flujo reputacional" — esqueleto completo del microservicio Reputación (Dockerfile, README, estructura de la app).
  - `ce14774` "Agregada funcionalidad apache pulsar" — infraestructura base del cluster (docker-compose, Helm chart para GKE).
- **Cómo colaboré con el resto del equipo:** mergeó su propio PR #7 a `main`. Este trabajo (Reputación + Pulsar) es la base que Jhoan y Frans extendieron después (migración de Proveedores a Pulsar, consumidor de `trabajos.finalizado` en Reputación).
