#!/bin/bash
# metadata_startup_script de esta VM: instala el binario de k6 (release
# oficial de GitHub, no el repo apt — evita depender de un keyserver
# alcanzable durante el arranque, mismo espíritu que la corrección ya
# documentada en pulsar-infra/gcp/templates/startup.sh.tpl para Docker) y
# copia esc-01.js + lib/config.js EMBEBIDOS TAL CUAL vía Terraform
# (file(), sin modificarlos) — mismo patrón que pulsar-infra/gcp/compute.tf
# usa para docker-compose.yml. Se ejecuta una sola vez al primer arranque.
set -euxo pipefail

curl -fsSL "https://github.com/grafana/k6/releases/download/${k6_version}/k6-${k6_version}-linux-amd64.tar.gz" \
  -o /tmp/k6.tar.gz
tar -xzf /tmp/k6.tar.gz -C /tmp
mv "/tmp/k6-${k6_version}-linux-amd64/k6" /usr/local/bin/k6
chmod +x /usr/local/bin/k6

mkdir -p /opt/k6-runner/lib

cat > /opt/k6-runner/esc-01.js <<'ESC01_EOF'
${esc01_content}
ESC01_EOF

cat > /opt/k6-runner/lib/config.js <<'CONFIG_EOF'
${config_content}
CONFIG_EOF

mkdir -p /opt/k6-runner/results
