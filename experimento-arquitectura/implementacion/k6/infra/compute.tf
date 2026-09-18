locals {
  zone = coalesce(var.zone, "${var.region}-a")

  esc01_content  = file("${path.module}/../esc-01.js")
  config_content = file("${path.module}/../lib/config.js")

  startup_script = templatefile("${path.module}/templates/startup.sh.tpl", {
    k6_version     = var.k6_version
    esc01_content  = local.esc01_content
    config_content = local.config_content
  })
}

resource "google_service_account" "k6_vm" {
  account_id   = "${var.entorno}-vm"
  display_name = "VM generadora de carga k6 (${var.entorno})"
}

# Alcance mínimo: esta VM solo genera tráfico HTTP saliente hacia URLs
# públicas de Cloud Run — no llama a ninguna otra API de GCP salvo su
# propio servidor de metadata (sin IAM) y logging/monitoring del agente
# de sistema.
resource "google_project_iam_member" "k6_vm_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.k6_vm.email}"
}

resource "google_project_iam_member" "k6_vm_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.k6_vm.email}"
}

resource "google_compute_instance" "k6_runner" {
  name         = "${var.entorno}-vm"
  machine_type = var.machine_type
  zone         = local.zone
  tags         = ["k6-runner"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = var.disk_size_gb
      type  = "pd-balanced"
    }
  }

  network_interface {
    network = "default"

    access_config {
      # IP externa efímera — necesaria para que el tráfico de carga salga
      # directo a internet (Cloud Run) sin depender de Direct VPC egress
      # ni de un Cloud NAT (que esta VM no necesita para nada más).
    }
  }

  service_account {
    email  = google_service_account.k6_vm.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = local.startup_script

  allow_stopping_for_update = true

  depends_on = [google_project_service.apis]
}
