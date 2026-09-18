# Esta VM solo necesita SALIR a internet (hacia las URLs públicas de Cloud
# Run) — el egress por defecto de la red "default" ya lo permite, sin
# necesidad de ninguna regla de firewall adicional (a diferencia de
# pulsar-infra/gcp, que sí necesita reglas de INGRESS porque otros
# servicios se conectan A esa VM). Acá no hace falta nada de eso: nadie se
# conecta a esta VM excepto quien la administra por SSH.

resource "google_compute_firewall" "k6_ssh_iap" {
  name    = "${var.entorno}-ssh-iap"
  network = "default"

  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"] # rango fijo de Google para el túnel IAP
  target_tags   = ["k6-runner"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_firewall" "k6_ssh_externo" {
  count   = length(var.admin_source_ranges) > 0 ? 1 : 0
  name    = "${var.entorno}-ssh-externo"
  network = "default"

  direction     = "INGRESS"
  source_ranges = var.admin_source_ranges
  target_tags   = ["k6-runner"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
