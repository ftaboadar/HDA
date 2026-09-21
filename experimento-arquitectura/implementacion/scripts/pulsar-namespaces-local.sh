#!/usr/bin/env bash
# Crea el tenant y los 8 namespaces de Pulsar en el cluster LOCAL
# (docker compose -f pulsar-infra/docker-compose.yml up -d). En GCP no hace falta:
# lo hace el startup script de la VM (pulsar-infra/gcp/templates/startup.sh.tpl).
# Lista de namespaces = CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §4. Idempotente.

set -euo pipefail
BROKER="${BROKER:-hda-pulsar-broker}"

echo "Esperando al broker ${BROKER}..."
for _ in $(seq 1 60); do
  curl -sf http://localhost:8080/admin/v2/brokers/health >/dev/null && break
  sleep 5
done

docker exec "$BROKER" bin/pulsar-admin tenants create hda --allowed-clusters cluster-hda 2>/dev/null || true
for ns in gestion-trabajos proveedores reputacion marketplace siniestros suscripciones pagos scoring; do
  docker exec "$BROKER" bin/pulsar-admin namespaces create "hda/${ns}" 2>/dev/null || true
done
docker exec "$BROKER" bin/pulsar-admin namespaces list hda
