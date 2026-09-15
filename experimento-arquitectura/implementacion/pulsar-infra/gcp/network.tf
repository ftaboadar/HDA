# Rango de la subred "default" del proyecto en esta región — usado en vez
# de 0.0.0.0/0 para las reglas de firewall de abajo, tal como pide la
# tarea. IMPORTANTE (ver DESPLIEGUE-GCP-INTEGRAL.md para el detalle
# completo): esto SOLO restringe de verdad el tráfico de Cloud Run si el
# servicio que llama a Pulsar tiene Direct VPC egress habilitado sobre
# esta misma subred (ver gestion-de-trabajos/infra/service.tf) — el
# egress serverless por defecto de Cloud Run NO se origina desde este
# rango, así que una regla de firewall limitada a este CIDR sin ese
# Direct VPC egress del lado del cliente simplemente bloquearía a Cloud
# Run también, no solo a "el resto de internet".
data "google_compute_subnetwork" "default" {
  name    = "default"
  region  = var.region
  project = var.project_id
}

resource "google_compute_firewall" "pulsar_vpc_only" {
  name    = "${var.entorno}-pulsar-vpc-only"
  network = "default"

  direction     = "INGRESS"
  source_ranges = [data.google_compute_subnetwork.default.ip_cidr_range]
  target_tags   = ["pulsar"]

  allow {
    protocol = "tcp"
    ports    = ["6650", "8080"]
  }
}

# Opcional: acceso de administración/debug a 8080 (admin REST) desde IPs
# puntuales fuera de la VPC (ej. la máquina de un desarrollador) — NO
# abre 6650 (protocolo binario) externamente por la misma razón que
# justifica no usar 0.0.0.0/0: no hay necesidad real de que un cliente
# fuera de GCP produzca/consuma directo contra este cluster de PoC.
resource "google_compute_firewall" "pulsar_admin_externo" {
  count   = length(var.admin_source_ranges) > 0 ? 1 : 0
  name    = "${var.entorno}-pulsar-admin-externo"
  network = "default"

  direction     = "INGRESS"
  source_ranges = var.admin_source_ranges
  target_tags   = ["pulsar"]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}

# SSH solo vía IAP (rango fijo de Google para el túnel de
# `gcloud compute ssh --tunnel-through-iap`), no 0.0.0.0/0 — necesario
# para poder operar/depurar la VM (ver comandos en
# DESPLIEGUE-GCP-INTEGRAL.md) sin exponer el puerto 22 a internet.
resource "google_compute_firewall" "pulsar_ssh_iap" {
  name    = "${var.entorno}-pulsar-ssh-iap"
  network = "default"

  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["pulsar"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
