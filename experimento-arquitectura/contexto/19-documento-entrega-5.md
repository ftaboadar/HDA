# Documento Final — Entrega 5: Refinamiento de la Arquitectura (Hogar de los Alpes)

Este documento consolida el trabajo arquitectónico, la implementación y los resultados empíricos de los experimentos realizados durante la Fase 5 para la plataforma Hogar de los Alpes (HdA).

---

## 1. Refinamiento de la Arquitectura
Durante la ejecución de los experimentos, la arquitectura base fue iterada. Los cambios puntuales entre el diseño original (Entregas previas) y esta versión final, incluyendo la adopción del **BFF** y el **Coordinador de Sagas**, así como sus motivaciones derivadas de los ensayos (k6/Newman), se detallan en el [Refinamiento de la Arquitectura (17-refinamiento-arquitectura.md)](17-refinamiento-arquitectura.md).

---

## 2. Decisiones Arquitectónicas y Justificación
Se adoptó un modelo basado en Arquitectura Hexagonal y DDD (Domain-Driven Design).
*   **Orquestación vs Coreografía (A22):** Se optó por una *Saga Orquestada* centralizada en *Gestión de Trabajos* para flujos multi-paso (Pagos, Reservas, Siniestros), sacrificando simplicidad inicial para ganar control y poder de compensación ante disputas (DISP-02).
*   **BFF REST (A25):** Único punto de ruteo que abstrae los 9 microservicios subyacentes, favoreciendo la seguridad, la trazabilidad del `correlation_id` y simplificando los clientes.
*   **Contratos JSON con Schema (A21):** Para Apache Pulsar se usó `JsonSchema` en vez de Avro/Protobuf para mantener legibilidad, manteniendo retrocompatibilidad (BACKWARD).
*   **Topología Descentralizada (A26):** Cada microservicio es dueño de su base de datos.
*   **Cloud Run Multi-Región (A29):** Estrategia para mitigar las cuotas de vCPU gratuitas y soportar el escenario de escalabilidad, distribuyendo los contenedores entre varias regiones.

---

## 3. Resultados de los Experimentos (Veredictos)
Tras el despliegue multi-región, los escenarios definidos en el `PLAN-EXPERIMENTOS.md` arrojaron:

1.  **JRN-02 / ESC-01 (Escalabilidad Siniestros):** **Aceptado.** Con un pico inyectado (4x) vía `k6`, los servicios escalaron hasta su `max_instances=2`. El p95 se sostuvo por debajo de 2.5s. Pulsar absorbió el *backlog* transitorio sin generar `503 Service Unavailable`.
2.  **JRN-03 / DISP-02 (Disponibilidad CRM):** **Aceptado.** Se inyectó una ráfaga de webhooks. El CRM limitado (100 rps) rechazó peticiones con HTTP 429. El *Circuit Breaker* en Gestión de Trabajos contuvo el golpe, y la cola de Pulsar reencoló con *exponential backoff*, resultando en 0% pérdida de datos.
3.  **JRN-04 / MOD-02 (Modificabilidad Pagos):** **Aceptado.** Añadir el ruteo hacia la pasarela de Brasil no afectó al núcleo. El patrón *Strategy* en Pagos permitió la extensibilidad en menos de 2 días-persona de esfuerzo.

---

## 4. Diseño Orientado al Dominio (DDD) por Servicio
Todos los microservicios respetan la regla de la cebolla (Domain, Application, Infrastructure):
*   **Gestión de Trabajos:** Agregado `Trabajo`. Contiene el *Saga Log* en su adaptador SQL. Comunica comandos a los demás servicios.
*   **Proveedores:** Agregados `Proveedor`, `Tecnico`, `Franja`. Dividido en módulos de Registro, Verificación, Agenda y Elegibilidad.
*   **Siniestros:** Agregado `Siniestro`. Implementa reglas lógicas para la aprobación en conjunto con la bolsa de la aseguradora.
*   **Pagos:** Implementa CQRS. Patrones *Strategy* y *Adapter* aíslan la conexión a Stripe/MercadoPago.
*   **Reputación, Suscripciones, Scoring, Marketplace:** Mantienen persistencias aisladas y reaccionan a los eventos de dominio (`trabajos.finalizado`, `elegibles.publicados`).

---

## 5. Topología de Datos y Base de Datos por Servicio
*   En cumplimiento del patrón *Database-per-service*, existen las bases `gestion_trabajos`, `siniestros`, `proveedores`, `suscripciones`, etc.
*   El **Saga Log** usa Event Sourcing parcial; registra transacciones *append-only* en `saga_log` y estado de máquina en `saga_instancia`.

---

## 6. Integración y Contratos Asíncronos
*   **Tipos de Mensajes:** Distinción clara entre *Comandos* (`RetenerPago`, emitidos por el orquestador y consumidos por un único Worker) y *Eventos* (`TrabajoFinalizado`, emitidos al terminar un caso de uso y consumidos por N workers mediante pub/sub).
*   **Versionamiento:** Regla de evolución `BACKWARD`. No se rompe el contrato existente.
*   El esquema asíncrono completo se encuentra consolidado en el estándar AsyncAPI: [hda-asyncapi.yaml](implementacion/asyncapi/hda-asyncapi.yaml).

---

## 7. Despliegue en GCP
La arquitectura se desplegó bajo el paradigma de Infraestructura como Código (Terraform) para garantizar repetibilidad:
*   **Cómputo:** Google Cloud Run (Auto-escalado, facturación por uso).
*   **Mensajería:** Apache Pulsar (Máquina virtual CE) por el soporte nativo multi-tenant.
*   **Persistencia:** Cloud SQL (PostgreSQL).
*   **Enlaces y Entregables:**
    *   **BFF URL Oficial:** `https://gestion-trabajos-poc-api-kgt57ziq4a-rj.a.run.app` *(Nota: El clúster se enciende únicamente a demanda para la sustentación)*.
    *   **Swagger/OpenAPI:** Exportado en `/docs` del BFF y cada microservicio.
    *   **Colección Postman:** Disponible en `postman/`.


---

## 8. Anexo: Evidencia Funcional (BFF y Postman)
Para evidenciar el correcto funcionamiento de los Journeys (JRN-01 a JRN-05) a través del BFF, se adjunta la colección oficial en `implementacion/journey/Journey E5.postman_collection.json`. A continuación, un ejemplo de la respuesta esperada al iniciar una transacción en el BFF (Paso 1 del Journey):

**Request (POST /v1/trabajos):**
```json
{
    "cliente_id": "CLI-9876",
    "tipo_servicio": "plomeria",
    "region": "CO",
    "detalles": "Fuga de agua en lavamanos"
}
```

**Response Exitosa (HTTP 202 Accepted):**
```json
{
    "mensaje": "Trabajo recibido. Saga iniciada.",
    "trabajo_id": "TRB-12345678",
    "saga_id": "SAGA-87654321",
    "correlation_id": "req-abc-123",
    "estado": "SOLICITADO"
}
```

### JRN-02: Pico de Siniestros
**Request (POST /v1/siniestros):**
```json
{
    "cliente_id": "CLI-5555",
    "propiedad_id": "PROP-999",
    "tipo_siniestro": "INUNDACION",
    "monto_estimado": 1500000
}
```
**Response (HTTP 202 Accepted):**
```json
{
    "mensaje": "Siniestro radicado, pendiente de reglas de aprobación.",
    "siniestro_id": "SIN-4040"
}
```

### JRN-03: Caída CRM y Disputa (Compensación)
**Request (POST /v1/trabajos/TRB-12345678/novedades):**
```json
{
    "tipo_novedad": "DISPUTA_CLIENTE",
    "descripcion": "El proveedor no llegó a la hora acordada."
}
```
**Response (HTTP 202 Accepted):**
```json
{
    "mensaje": "Novedad recibida. El coordinador ha iniciado la compensación (reembolso) de la Saga.",
    "estado_saga": "COMPENSANDO"
}
```

### JRN-04: Transacción Internacional (Brasil)
**Request (POST /v1/trabajos) - Forzando MercadoPago:**
```json
{
    "cliente_id": "BR-001",
    "tipo_servicio": "limpieza",
    "region": "BR",
    "metodo_pago": "MERCADOPAGO"
}
```
**Response (HTTP 202 Accepted):**
```json
{
    "mensaje": "Trabajo recibido. Saga iniciada en región BR.",
    "trabajo_id": "TRB-99998888",
    "saga_id": "SAGA-77776666",
    "pasarela_asignada": "MercadoPagoAdapter"
}
```

### JRN-05: Fan-Out Background (Scoring)
**Request (GET /v1/scoring/clientes/CLI-9876):**
```json
// Sin body (GET)
```
**Response (HTTP 200 OK):**
```json
{
    "cliente_id": "CLI-9876",
    "score_actual": 850,
    "ultimo_evento_procesado": "TrabajoFinalizado"
}
```

*Nota: La ejecución completa de todos estos casos, así como las consultas a la base de datos (Saga Log), se demostrarán en vivo durante el Video de Sustentación utilizando la colección Postman provista en el repositorio.*

