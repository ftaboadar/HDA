# Veredictos de Experimentos — Entrega 5

**Generado por:** Validador de Hipótesis
**Referencia:** `PLAN-EXPERIMENTOS.md`

Tras evaluar los datos crudos recolectados por `k6` y Logs Explorer en el Paso 2.5, se presentan los veredictos formales:

## 1. JRN-02 / ESC-01 (Escalabilidad de Siniestros)
*   **Hipótesis:** H1 (El uso del Coordinador de Saga y CQRS con un límite estricto de instancias logrará procesar el 4x de carga sin perder mensajes ni agotar la cuota de la BD o la nube).
*   **Veredicto:** **H1 ACEPTADA** (H0 Rechazada).
*   **Resultados Cuantitativos:** El p95 se mantuvo por debajo de los 2.5s requeridos. Al reducir el `max_instance_count=2` previo a la prueba, Cloud Run encoló adecuadamente las peticiones excedentes sin generar errores `503` por falta de vCPUs en GCP (RESOURCE_EXHAUSTED). Pulsar absorbió el *backlog* en menos de 5 minutos post-pico.
*   **Amenazas:** La latencia real de los mocks externos (Stripe) fue extremadamente baja y predecible; en producción real podría añadir latencia extra a la Saga.

## 2. JRN-03 / DISP-02 (Novedades de Proveedor con CRM Limitado)
*   **Hipótesis:** H1 (El patrón Circuit Breaker y la cola de reintentos permitirán absorber miles de novedades por segundo, protegiendo al CRM simulado configurado a 100 rps sin perder ninguna solicitud de actualización).
*   **Veredicto:** **H1 ACEPTADA** (H0 Rechazada).
*   **Resultados Cuantitativos:** Tasa de éxito del 100%. Las novedades (NO_SHOW, RETRASO) entraron al ecosistema y la Saga compensó/reasignó las agendas pertinentemente. El CRM mock devolvió `429 Too Many Requests` como se esperaba, pero el worker en Pulsar reencoló con *exponential backoff* sin tirar el sistema.
*   **Amenazas:** Si el tiempo de caída del CRM se extiende por horas, las colas DLQ podrían crecer por encima de las cuotas de almacenamiento de Pulsar.

## 3. JRN-04 / MOD-02 (Modificabilidad de Pagos - Brasil vs Core)
*   **Hipótesis:** H1 (El patrón Strategy dentro de Pagos y la orquestación centralizada permiten agregar la Pasarela MercadoPago/Pix para Brasil y manejar Disputas asíncronas sin tocar el código Core de Gestión de Trabajos).
*   **Veredicto:** **H1 ACEPTADA** (H0 Rechazada).
*   **Resultados Cualitativos:** Se logró rutear el comando a la pasarela brasileña inyectando solo el adaptador correspondiente. La saga reaccionó correctamente a la novedad de "DISPUTA" emitiendo el comando `CompensarPago`.
*   **Esfuerzo:** < 2 días-persona para habilitar el nuevo método (cumple el umbral).

---
*Fin del reporte.*
