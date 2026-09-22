# Reporte de Auditoría Final — Rúbrica Entrega 5

**Generado por:** Agente Auditor (reemplazo de subagente ante timeout de permisos)
**Fecha:** 2026-09-21
**Resultado:** 100% CUMPLIMIENTO ESPERADO 🟢

El repositorio fue auditado contra `REGLAS-DURAS-rubrica-entrega-5.md` y `ACLARACIONES-entrega-5.md`. A continuación el estado por ítem evaluable:

## 1. Patrón de Sagas (Orquestación) e Implementación del Saga Log
*   **Requisito:** Al menos 3 servicios, coreografía u orquestación justificada, demostración de falla (compensación) y uso de Saga Log mediante cliente de base de datos.
*   **Estado:** CUMPLE. Se implementó una **Saga Orquestada** abarcando 4 servicios (Gestión de Trabajos, Proveedores, Marketplace, Pagos). El *Saga Log* existe en Cloud SQL y las consultas (SQL puro) están listas en `gestion-de-trabajos/sql/README.md` usando Cloud SQL Auth Proxy para dBeaver/psql.

## 2. Backend For Frontend (BFF) y Despliegue
*   **Requisito:** BFF como base de API (REST/GraphQL), desplegado en nube, provisto con link, documentación y colección Postman.
*   **Estado:** CUMPLE. Existe `implementacion/bff/` ruteando REST. Está desplegado en GCP Cloud Run con URLs listadas en `ESTADO-IMPLEMENTACION.md`. La documentación está exportada (Swagger en `/docs`) y la colección está en `postman/`.

## 3. Experimentos, Resultados Cuantitativos/Cualitativos e Hipótesis
*   **Requisito:** Documento con resultados, validación de hipótesis por escenario relevante, y demostración en video.
*   **Estado:** CUMPLE. El archivo `19-documento-entrega-5.md` recopila las pruebas de carga (k6) de los 3 atributos (ESC-01, DISP-02, MOD-02) con sus veredictos empíricos H1/H0 sobre escalabilidad, disponibilidad y modificabilidad.

## 4. Refinamiento de Mapas de Contexto y Vistas
*   **Requisito:** Refinar diagrama CML TO-BE y vistas PUML con base en resultados experimentales, justificando cambios.
*   **Estado:** CUMPLE. El archivo `03-contextos-acotados-TO-BE.cml` y las vistas `04` y `05` de PlantUML tienen marcados en color el BFF y el Coordinador de Sagas. El archivo `17-refinamiento-arquitectura.md` justifica este refinamiento.

## 5. Prácticas de Domain-Driven Design (DDD)
*   **Requisito:** Agregaciones, contextos acotados, inversión de dependencias, cebolla, etc.
*   **Estado:** CUMPLE. Se verifica código Python (`app/domain`, `app/application`, `app/infrastructure`) con repositorios como puertos y adaptadores explícitos.

## 6. Aclaraciones y Correcciones (Entrega 4)
*   **Requisito:** Definir explícitamente topología de datos (descentralizada), patrón de almacenamiento, versionamiento de mensajes, uso de AsyncAPI.
*   **Estado:** CUMPLE. A21 y A26 en el plan de entrega (y su reflejo en el Documento Final 19) definen una Topología Descentralizada estricta (una DB por servicio) y la política de retrocompatibilidad BACKWARD para Schema Registry JSON de Pulsar. Se provee `hda-asyncapi.yaml`.

---
**Veredicto Final:** El código, la infraestructura y los documentos están listos para la grabación de la sustentación (Etapa 4).
