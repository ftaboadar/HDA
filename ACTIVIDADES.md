# Registro de Actividades del Equipo

## Entrega 5 (Arquitectura por Escenarios y Journeys)

En esta entrega final, el equipo dividió las labores para cubrir el ciclo completo de diseño, implementación y experimentación sobre la arquitectura consolidada de Hogar de los Alpes.

### Jhoan
*   **Rol:** Implementación, Integración y Pruebas de Carga.
*   **Actividades:**
    *   Lideró la implementación (Pasos 1.2 al 1.11) de los microservicios usando DDD y Arquitectura Hexagonal.
    *   Configuró los scripts automatizados de despliegue y apagado (`desplegar-todo.sh`, `destruir-todo.sh`) hacia Google Cloud.
    *   Creó y desplegó el BFF (API Gateway) como fachada central.
    *   Ejecutó y analizó el experimento **ESC-01 (JRN-02)** inyectando el pico de Siniestros mediante `k6`.

### Frans
*   **Rol:** Orquestación (Sagas) y Experimentos de Disponibilidad.
*   **Actividades:**
    *   Diseñó la máquina de estados y el motor de Workflow (Saga Orquestada) en Gestión de Trabajos.
    *   Consolidó el almacenamiento del *Saga Log* en Cloud SQL y documentó el acceso seguro vía Auth Proxy.
    *   Planteó y validó las hipótesis H1/H0 del plan de experimentación.
    *   Ejecutó y analizó el experimento **DISP-02 (JRN-03)** con el CRM limitado, comprobando el Circuit Breaker.

### Daniel
*   **Rol:** Arquitectura, Documentación y Contratos.
*   **Actividades:**
    *   Consolidó el esquema asíncrono y el versionamiento (`hda-asyncapi.yaml`) usando JSON Schema en Pulsar.
    *   Refinó las vistas CML y UML para la Entrega 5 (BFF y Coordinador de Sagas).
    *   Redactó el Documento Final y supervisó la estructura DDD por servicio (repositorios, puertos y módulos).
    *   Ejecutó y analizó el experimento **MOD-02 (JRN-04)** (Pasarela Brasil), demostrando el patrón Strategy.
