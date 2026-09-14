# Mocks de Pagos — Stripe y MercadoPago

Dobles HTTP de los dos proveedores de pagos que consumiría el módulo ACL de Pagos dentro de
**Gestión de Trabajos** (ver `../../contexto/12-plan-entrega-4.md`, sección 0.1: Pagos es un
`GENERIC_SUBDOMAIN` externo — no un microservicio propio de Hogar de los Alpes — y este mock cumple
el mismo rol que los mocks de Policía/RUES/CONTE en `../DISP-03/app/mocks/`).

**No son un microservicio de dominio.** Son sistemas externos simulados, consumidos vía HTTP
síncrono por el Adapter `PasarelaDePago` que construye Gestión de Trabajos — la única excepción
permitida a la regla dura de comunicación por eventos (sección 3.1 del plan), porque no cruzan un
Bounded Context propio, cruzan hacia un sistema comprado.

## Por qué dos mocks distintos (y no uno parametrizado)

A diferencia de los mocks de Policía/RUES/CONTE en DISP-03 (que comparten forma de
petición/respuesta y solo cambian de "personalidad" vía `MOCK_NAME`), Stripe y MercadoPago
deliberadamente **no comparten forma**:

| | Stripe (`POST /charges`) | MercadoPago (`POST /payments`) |
|---|---|---|
| Unidad de monto | Centavos (`amount: 100` = $1.00) | Unidades completas (`transaction_amount: 15000.0`) |
| Identificador de la transacción | `id` con prefijo `ch_` (string) | `id` numérico |
| Campo de estado | `status` en inglés (`succeeded`) | `status` + `status_detail` en español (`approved`/`accredited`) |

Esa diferencia real es justo lo que MOD-02 valida: el Adapter `PasarelaDePago` (Strategy
`ReglaRegional` Colombia→Stripe / Brasil→MercadoPago, dentro de Gestión de Trabajos) debe absorberla
sin que el core del servicio conozca ninguna de las dos formas. Si ambos mocks respondieran igual,
no habría ninguna diferencia real que el Adapter estuviera absorbiendo.

## Estructura

```
app/
  common.py             estado + endpoint de control compartido (/_control/config), mismo patrón
                         que implementacion/DISP-03/app/mocks/main.py
  stripe_mock.py         FastAPI — POST /charges
  mercadopago_mock.py     FastAPI — POST /payments
```

## Control de fallas/latencia (idéntico patrón a DISP-03)

Cada mock expone:

- `GET /salud`
- `GET /_control/estado`
- `POST /_control/config` — `{"modo": "ok" | "error_parcial" | "caido" | "timeout", "latencia_ms": int, "tasa_error": float}`

## Correr localmente

```bash
docker compose up -d --build
curl -X POST http://localhost:9100/charges \
  -H "Content-Type: application/json" \
  -d '{"amount": 150000, "proveedor_id": "prov-1"}'

curl -X POST http://localhost:9101/payments \
  -H "Content-Type: application/json" \
  -d '{"transaction_amount": 1500.0, "proveedor_id": "prov-1"}'

curl -X POST http://localhost:9100/_control/config \
  -H "Content-Type: application/json" \
  -d '{"modo": "caido"}'

docker compose down
```

Puertos: Stripe `9100`, MercadoPago `9101` — ambos exponen su servicio interno en `8000`, mapeado
distinto en el host para poder correr los dos a la vez sin chocar.
