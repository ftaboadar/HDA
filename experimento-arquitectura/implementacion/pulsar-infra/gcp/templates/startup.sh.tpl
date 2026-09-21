#!/bin/bash
# metadata_startup_script de la VM de este stack — instala Docker, copia
# el docker-compose.yml REAL de pulsar-infra/ (embebido tal cual por
# Terraform vía file(), sin modificarlo — ver compute.tf) más el override
# de este stack (ver templates/docker-compose.override.yml) y levanta el
# cluster. Se ejecuta una sola vez al primer arranque de la VM (comportamiento
# estándar de metadata_startup_script en Debian/Ubuntu vía el paquete
# google-guest-agent).
set -euxo pipefail

# CORRECCIÓN (encontrada corriendo un apply real, no en validate/plan):
# `docker-compose-plugin` NO existe en los repos de Debian por defecto —
# solo en el repo propio de Docker. `apt-get install -y docker.io
# docker-compose-plugin` fallaba con "Unable to locate package" y, por
# `set -euxo pipefail`, abortaba el script entero ahí mismo — Docker nunca
# llegaba a instalarse ni a arrancar. Se usa el script oficial de Docker
# (get.docker.com), que agrega el repo correcto e instala
# docker-ce/docker-ce-cli/containerd.io/docker-compose-plugin de una vez,
# ya probado para Debian/Ubuntu.
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

mkdir -p /opt/pulsar-infra

cat > /opt/pulsar-infra/docker-compose.yml <<'COMPOSE_EOF'
${compose_content}
COMPOSE_EOF

cat > /opt/pulsar-infra/docker-compose.override.yml <<'OVERRIDE_EOF'
${override_content}
OVERRIDE_EOF

# IP interna real de esta VM, vía el servidor de metadata de GCP — no se
# puede conocer desde Terraform dentro de este mismo startup script (la
# instancia todavía no existe cuando Terraform renderiza esta plantilla).
INTERNAL_IP=$(curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/ip")

sed -i "s/__ADVERTISED_IP__/$INTERNAL_IP/" /opt/pulsar-infra/docker-compose.override.yml

cd /opt/pulsar-infra
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d

# Tenant y namespaces del proyecto. Antes era un paso manual (bug 4 de DESPLIEGUE-GCP-INTEGRAL.md:
# sin ellos publicar falla con TopicNotFound). Lista = CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §4.
# Espera a que el broker responda (hasta 10 min) y crea todo de forma idempotente (|| true).
for i in $(seq 1 60); do
  curl -sf http://localhost:8080/admin/v2/brokers/health >/dev/null && break
  sleep 10
done
docker exec hda-pulsar-broker bin/pulsar-admin tenants create hda --allowed-clusters cluster-hda || true
for ns in gestion-trabajos proveedores reputacion marketplace siniestros suscripciones pagos scoring; do
  docker exec hda-pulsar-broker bin/pulsar-admin namespaces create hda/$ns || true
done
# Marca que scripts/desplegar-todo.sh espera antes de desplegar los servicios.
touch /opt/pulsar-infra/namespaces-listos
