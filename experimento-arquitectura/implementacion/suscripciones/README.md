# Suscripciones

Microservicio para gestionar los ciclos de suscripción y contratos.

## Módulos
- `ciclo_suscripcion`: Contiene la lógica de negocio para la generación y continuidad de suscripciones.

## Eventos que consume
- `TrabajoFinalizado` (desde `gestion-trabajos`). Se consume en modo fan-out para mantener la continuidad del proveedor.

## Eventos que publica
- `CicloSuscripcion`: Generado cuando un ciclo nuevo debe ser procesado y un trabajo debe ser creado.

## Decisiones DDD
- **A13**: Continuidad del proveedor. El mismo proveedor del primer ciclo se mantiene en los siguientes.
- **A14**: Reserva recurrente. La franja se bloquea para todo el periodo.

## Cómo correr
`docker-compose up`

