#!/usr/bin/env bash
# Presupuesto de la cuota regional de CPU de Cloud Run para la Entrega 5.
#
# Todos los servicios van en UNA región (southamerica-east1) y un proyecto nuevo trae 20 vCPU de "Total
# CPU allocation" por región (observado en hogaralpes; el valor real se ve en Quotas & System Limits). Cloud
# Run calcula el máximo de instancias de un servicio como cuota regional / CPU por instancia, y las
# instancias de TODOS los servicios de la región suman contra la misma cuota.
#
# Calcula con la tabla de abajo (diseño de la Entrega 5: 9 servicios, la mayoría con api + worker, más
# mocks y Grafana):
#   - PISO  = lo que está encendido siempre (min_instancias × cpu): es lo que se paga y se ocupa aunque
#             nadie use el sistema (los workers de Pulsar necesitan min=1 y CPU siempre asignada).
#   - PICO  = max_instancias × cpu de todos los servicios a la vez (cota superior; nunca ocurre completa).
# y dice cuántas vCPU hay que pedirle a Google si el perfil no cabe en la cuota.
#
# Uso:  CUOTA_VCPU=20 ./presupuesto-cuota.sh            (tabla completa)
#       CUOTA_VCPU=20 ./presupuesto-cuota.sh --verificar (sale con 1 si el piso no cabe)
#
# Al agregar un servicio: agrégalo a TABLA (mismos valores que pone en su stack de Terraform).

set -euo pipefail
CUOTA_VCPU="${CUOTA_VCPU:-20}"

# servicio | cpu | min_demo | max_demo | min_carga | max_carga
#   demo  = lo normal (sustentación, pruebas de humo)
#   carga = corrida de ESC-01/JRN-02 (pico 4x): los 6 consumidores de trabajos.finalizado deben estar vivos
TABLA='bff|1|0|2|1|2
gt-api|2|0|2|1|2
gt-worker|1|1|2|1|2
proveedores-api|1|0|2|0|2
proveedores-worker|1|1|2|1|2
pagos-api|1|0|2|0|2
pagos-worker|1|1|1|1|2
reputacion-api|1|0|1|0|1
reputacion-worker|1|1|1|1|2
marketplace-api|1|0|2|0|2
marketplace-worker|1|1|1|1|2
siniestros-api|1|0|2|1|2
siniestros-worker|1|1|1|1|2
suscripciones-api|1|0|1|0|1
suscripciones-worker|1|1|1|1|2
scoring-api|1|0|1|0|1
scoring-worker|1|1|1|1|2
mock-crm|1|1|1|1|1
mock-policia|1|0|1|0|1
mock-rues|1|0|1|0|1
mock-certificadora|1|0|1|0|1
mock-stripe|1|0|1|0|1
mock-mercadopago|1|0|1|0|1
grafana|1|1|1|1|1'

echo "Cuota regional de CPU de Cloud Run: ${CUOTA_VCPU} vCPU"
printf '\n%-22s %4s | %-9s %-9s | %-9s %-9s\n' "servicio" "cpu" "demo min" "demo max" "carga min" "carga max"
echo "$TABLA" | awk -F'|' '{ printf "%-22s %4s | %-9s %-9s | %-9s %-9s\n", $1, $2, $3*$2, $4*$2, $5*$2, $6*$2 }'
echo "(cifras en vCPU = instancias × cpu)"

calc() { # <columna min> <columna max>
  echo "$TABLA" | awk -F'|' -v cmin="$1" -v cmax="$2" '{ piso += $cmin*$2; pico += $cmax*$2 } END { printf "%d %d", piso, pico }'
}
read -r PISO_DEMO PICO_DEMO <<<"$(calc 3 4)"
read -r PISO_CARGA PICO_CARGA <<<"$(calc 5 6)"
SERVICIOS="$(echo "$TABLA" | wc -l | tr -d ' ')"

echo
echo "Servicios de Cloud Run: ${SERVICIOS}"
printf '%-8s piso %3d vCPU (%3d%% de la cuota) · pico teórico %3d vCPU\n' "demo" "$PISO_DEMO" $((PISO_DEMO * 100 / CUOTA_VCPU)) "$PICO_DEMO"
printf '%-8s piso %3d vCPU (%3d%% de la cuota) · pico teórico %3d vCPU\n' "carga" "$PISO_CARGA" $((PISO_CARGA * 100 / CUOTA_VCPU)) "$PICO_CARGA"

# Regla: el piso no puede pasar del 60 % de la cuota, o no queda margen para escalar (el autoscaler falla con
# "no available instance"). El pico teórico no tiene que caber: los servicios no llegan al máximo a la vez.
LIMITE_PISO=$((CUOTA_VCPU * 60 / 100))
rc=0
echo
if [ "$PISO_DEMO" -gt "$LIMITE_PISO" ]; then
  echo "✗ demo: el piso (${PISO_DEMO}) supera el 60 % de la cuota (${LIMITE_PISO}): no queda margen para escalar."
  echo "  Pide más cuota, o baja min_instancias / cpu de los workers (ver CONVENCIONES §6, regla de cuota)."
  rc=1
else
  echo "✓ demo: el piso cabe con margen (${PISO_DEMO} ≤ ${LIMITE_PISO})."
fi
if [ "$PISO_CARGA" -gt "$LIMITE_PISO" ]; then
  echo "✗ carga: el piso (${PISO_CARGA}) supera el 60 % de la cuota (${LIMITE_PISO})."
  rc=1
fi
if [ "$PICO_CARGA" -le "$CUOTA_VCPU" ]; then
  echo "✓ carga: el pico teórico cabe en la cuota."
else
  # margen del 25 % sobre el pico de la corrida de carga (instancias que arrancan mientras otras se apagan)
  PEDIR=$(((PICO_CARGA * 125 + 99) / 100))
  echo "⚠ carga: el pico teórico (${PICO_CARGA}) no cabe en ${CUOTA_VCPU}: sin más cuota la corrida de ESC-01 no se puede"
  echo "  hacer a esta escala. Pide ~${PEDIR} vCPU (pico + 25 %) en Quotas & System Limits → 'Total CPU allocation, per"
  echo "  project per region' (Cloud Run Admin API, southamerica-east1). La aprobación no es inmediata: pídela ya."
fi

if [ "${1:-}" = "--verificar" ]; then exit "$rc"; fi
