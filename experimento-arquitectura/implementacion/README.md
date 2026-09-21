# Hogar de los Alpes — POC de Experimentación (Entrega Parcial)

## Entrega 5 (en curso): un solo journey

Los 4 escenarios de abajo se midieron **sueltos**. La Entrega 5 los conecta en un journey de negocio
entre 8 microservicios (se suman `marketplace/`, `siniestros/`, `suscripciones/` y `scoring/`):
proveedor verificado (DISP-03) → solicitud → trabajo creado y asignado (ESC-01) → novedades hacia el CRM
(DISP-02) → trabajo finalizado → pago con regla regional y pasarela (MOD-02) → calificación.

- **Qué existe hoy y qué se puede desplegar: [`ESTADO-IMPLEMENTACION.md`](ESTADO-IMPLEMENTACION.md)**
- Qué se construye: [`../contexto/15-arquitectura-entrega-5.md`](../contexto/15-arquitectura-entrega-5.md)
- Cómo se construye y despliega: [`CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`](CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md)
- Montar/apagar todo en GCP: [`DESPLIEGUE-GCP-INTEGRAL.md`](DESPLIEGUE-GCP-INTEGRAL.md)

## Escenarios de calidad validados

Uno por cada atributo de calidad acordado con el profesor, sobre la cadena de transacción larga
**Gestión de Trabajos → Proveedores → Pagos**, más Reputación como consumidor independiente (resultados de la
entrega parcial / Entrega 4).

| Escenario | Atributo | Qué prueba | ¿Pasa su umbral? |
|---|---|---|---|
| **ESC-01** | Escalabilidad | Pico 4x de siniestros — publicación async y consumo paralelo del tópico `trabajos.finalizado` | ⚠️ Mejoró de 14.2s a **5.2s de p95** (0% de fallo) tras aislar 3 cuellos de botella reales en cadena (sobresuscripción de conexiones, cold start, CPU de Cloud SQL y de Cloud Run) — **sigue por encima del umbral de <2s**. Ver `RESULTADOS-ESCALABILIDAD-GCP.md` |
| **DISP-02** | Disponibilidad | Throttling de Novedades hacia el CRM mockeado, sin perder mensajes bajo rate-limiting | ✅ **100.0%** entregadas (2000/2000, 0 agotadas) — reverificado de forma independiente. Ver `RESULTADOS-DISP02.md` |
| **DISP-03** | Disponibilidad | Verificación de proveedores ante falla de sistemas externos (Policía/RUES/Certificadora) | ✅ 11/13 checks en GCP real (las 2 diferencias son de latencia geográfica, no del mecanismo). Ver `proveedores/RESULTADOS-DISP03.md` |
| **MOD-02** | Modificabilidad | Extensión de reglas regionales y pasarelas de pago (Brasil/MercadoPago) sin tocar Colombia/Stripe ni el core | ✅ 17/17 pruebas — demostrado a nivel de código real. Ver `RESULTADOS-MOD02.md` |

## Estructura del proyecto

```
experimento-arquitectura/implementacion/
├── gestion-de-trabajos/   Publica trabajos.finalizado (ESC-01); Novedades + Throttler (DISP-02)
├── proveedores/           Verificación de proveedores — agregado Verificacion, DDD/hexagonal (DISP-03)
├── pagos/                 Microservicio independiente — Strategy (ReglaRegional) + Adapter (PasarelaDePago) (MOD-02)
├── reputacion/            Consumidor de trabajos.finalizado, Event Sourcing
├── pulsar-infra/          Cluster de Apache Pulsar (Zookeeper + BookKeeper + Broker) — local y GKE
├── mocks-crm/             Mock de "Gestión de Agentes (CRM SaaS)" — usado por DISP-02
├── mocks-pagos/           Mocks de Stripe y MercadoPago — usados por MOD-02
├── observabilidad/        Terraform de Grafana
├── infra-modules/         Módulo Terraform reusable (Cloud Run + IAM + Cloud SQL)
├── k6/                    Scripts de carga (ESC-01) y resultados capturados
└── asyncapi/              Definición del esquema de eventos (hda-asyncapi.yaml)
```

## Cómo desplegar localmente

1. Levantar el cluster de Pulsar:
   ```bash
   docker compose -f pulsar-infra/docker-compose.yml up -d
   ```
2. Por cada microservicio (`gestion-de-trabajos`, `proveedores`, `pagos`, `reputacion`), levantar
   su propio `docker-compose.yml`:
   ```bash
   docker compose -f <microservicio>/docker-compose.yml up -d --build
   ```
   `gestion-de-trabajos` tiene además `docker-compose.disp02.yml`, que suma el mock de CRM
   (`mocks-crm`) necesario para correr la prueba de DISP-02.
3. Correr las pruebas de cada microservicio:
   ```bash
   pytest <microservicio>/tests/unit -v
   ```
4. Correr la carga de ESC-01:
   ```bash
   k6 run k6/esc-01.js
   ```

## Resultados

- [`proveedores/RESULTADOS-DISP03.md`](proveedores/RESULTADOS-DISP03.md)
- [`RESULTADOS-DISP02.md`](RESULTADOS-DISP02.md)
- [`RESULTADOS-ESCALABILIDAD-GCP.md`](RESULTADOS-ESCALABILIDAD-GCP.md)
- [`RESULTADOS-MOD02.md`](RESULTADOS-MOD02.md)

Ver también [`ACTIVIDADES.md`](../../ACTIVIDADES.md) (raíz del repo) para la contribución de cada
miembro del equipo.
