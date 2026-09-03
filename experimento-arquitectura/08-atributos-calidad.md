# Hogar de los Alpes (HdA) — Entrega 2: Atributos de Calidad Prioritarios

## Selección

Se priorizan **3 atributos de calidad** para guiar el diseño táctico (TO-BE):

1. **Modificabilidad**
2. **Escalabilidad**
3. **Disponibilidad / Elasticidad ante picos de carga**

## Justificación de la selección

No se eligieron al azar: son los **tres únicos atributos que explican por qué se tomó
cada decisión arquitectónica** ya documentada en los diagramas de Contexto, Módulo y
C&C. Cada patrón usado (microservicios por Bounded Context, arquitectura orientada a
eventos, ACL hacia SaaS, circuit breaker, DLQ, auto-scaling) es una respuesta directa
a uno de estos tres atributos:

| Atributo | Evidencia en el enunciado | Patrón que lo resuelve |
|---|---|---|
| **Modificabilidad** | "Desarrollar nuevas capacidades es cada vez más difícil y demorado: despliegues de 3-4 horas, semanas de QA y equipos que se bloquean entre sí al compartir una misma fuente de código" | Microservicios por Bounded Context (1 servicio = 1 equipo = 1 despliegue independiente) |
| **Escalabilidad** | Expansión a México/Brasil/Argentina: se espera **triplicar** el volumen (12.000 → 36.000 trabajos/día) y **duplicar** ingeniería (50 → 100) en 3 años/18 meses | Microservicios con escalado horizontal independiente por servicio; equipos autónomos que escalan sin coordinarse |
| **Disponibilidad / Elasticidad** | "Un evento climático... puede multiplicar los siniestros de un día para otro" (hasta 4x en 48h); "SLA en riesgo" mencionado en el tablero de Siniestros; 5 sistemas SaaS/ERP externos de terceros fuera de nuestro control | Arquitectura orientada a eventos (desacople productor/consumidor), ACL + circuit breaker por integración externa, DLQ para picos |

**Atributos considerados y descartados como prioritarios (no architecturally-significant
para el TO-BE):**
- **Seguridad**: es crítica para el negocio (verificación de antecedentes, datos
  financieros de Fintech/Scoring), pero se resuelve principalmente con controles
  *tácticos* dentro de cada servicio (auth, cifrado, verificación de identidad) y no
  cambia la forma macro de la arquitectura — no aparece como driver de ningún patrón
  estructural en los diagramas.
- **Interoperabilidad multi-país**: ya está resuelta a nivel de modelado de dominio
  (cada Partner/país es una instancia del mismo Bounded Context `Siniestros`), no
  exige un atributo de calidad transversal adicional sobre la arquitectura ya definida.

## Árbol de utilidad (estilo ATAM)

Formato de prioridad: **(Importancia para el negocio, Dificultad técnica)** — H=Alta, M=Media, L=Baja.

```
Utilidad
│
├── Modificabilidad
│   ├── Despliegue independiente
│   │   └── "Un desarrollador cambia la lógica de cotización de Marketplace y la
│   │        despliega a producción sin coordinar con Proveedores ni Siniestros,
│   │        y sin re-testear el monolito completo."                         (H, H)
│   ├── Aislamiento entre equipos
│   │   └── "Los equipos de Fintech y Proveedores modifican su servicio en la
│   │        misma semana sin bloquearse por compartir código/BD."           (H, M)
│   └── Extensibilidad a nuevas líneas de negocio
│       └── "Se agrega el dominio de Suscripciones (servicios recurrentes) como
│            Bounded Context nuevo, sin modificar Gestión de Trabajos."       (H, M)
│
├── Escalabilidad
│   ├── Escalabilidad de carga transaccional
│   │   └── "El volumen de trabajos/día crece 3x (12.000→36.000) por la
│   │        expansión a 3 países, sin degradar tiempos de respuesta."       (H, H)
│   ├── Escalabilidad de equipos de ingeniería
│   │   └── "El equipo de ingeniería se duplica (50→100) y cada equipo escala
│   │        y despliega su propio servicio sin coordinar con los demás."     (M, M)
│   └── Escalabilidad por nuevo partner/país
│       └── "Se integra un nuevo partner B2B2C sin modificar el código de los
│            partners existentes."                                           (M, L)
│
└── Disponibilidad / Elasticidad ante picos
    ├── Tolerancia a picos de carga (4x/48h)
    │   └── "Un evento climático dispara siniestros hasta 4x en 48 horas; el
    │        sistema sigue procesando Marketplace y Suscripciones sin
    │        degradación perceptible."                                       (H, H)
    ├── Aislamiento de fallos de terceros
    │   └── "La pasarela de pagos o el CRM de agentes presentan una caída o
    │        alta latencia; Gestión de Trabajos sigue operando (encola /
    │        reintenta) sin bloquear la creación de nuevos Trabajos."         (H, H)
    └── Recuperación ante fallos de procesamiento de eventos
        └── "Un evento de Trabajo falla su procesamiento repetidamente
             (payload corrupto); se envía a una Dead Letter Queue sin
             bloquear el resto de la cola."                                   (M, M)
```

Los tres escenarios marcados **(H, H)** — despliegue independiente, carga
transaccional 3x, y picos de siniestros 4x — son los que más directamente motivan
las decisiones estructurales ya tomadas: la partición en microservicios por Bounded
Context, y la arquitectura orientada a eventos con ACL/circuit breaker/DLQ hacia los
sistemas externos, respectivamente.
