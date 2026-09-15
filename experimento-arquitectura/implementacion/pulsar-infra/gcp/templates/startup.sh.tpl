#!/bin/bash
# metadata_startup_script de la VM de este stack — instala Docker, copia
# el docker-compose.yml REAL de pulsar-infra/ (embebido tal cual por
# Terraform vía file(), sin modificarlo — ver compute.tf) más el override
# de este stack (ver templates/docker-compose.override.yml) y levanta el
# cluster. Se ejecuta una sola vez al primer arranque de la VM (comportamiento
# estándar de metadata_startup_script en Debian/Ubuntu vía el paquete
# google-guest-agent).
set -euxo pipefail

apt-get update
apt-get install -y docker.io docker-compose-plugin
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
