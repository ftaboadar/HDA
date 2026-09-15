locals {
  zone = coalesce(var.zone, "${var.region}-a")

  # Embebido directo del docker-compose.yml real (NO se modifica ese
  # archivo — instrucción explícita de la tarea) vía file(), en vez de
  # subirlo a un bucket de GCS + gsutil cp desde el startup script: para
  # un solo archivo de ~4KB que no cambia con el ciclo de vida de la VM,
  # embeberlo en el propio metadata_startup_script es más simple y no
  # depende de que la VM tenga permisos de Storage ni de que el bucket
  # exista antes que la VM (un recurso menos, un punto de falla menos).
  compose_content  = file("${path.module}/../docker-compose.yml")
  override_content = file("${path.module}/templates/docker-compose.override.yml")

  startup_script = templatefile("${path.module}/templates/startup.sh.tpl", {
    compose_content  = local.compose_content
    override_content = local.override_content
  })
}

resource "google_service_account" "pulsar_vm" {
  account_id   = "${var.entorno}-vm"
  display_name = "VM del cluster Pulsar (${var.entorno})"
}

# Alcance mínimo: esta VM no llama a ninguna otra API de GCP más allá de
# su propio servidor de metadata (que no requiere IAM) — logging/monitoring
# de agente de sistema es lo único que de verdad usa la SA adjunta.
resource "google_project_iam_member" "pulsar_vm_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.pulsar_vm.email}"
}

resource "google_project_iam_member" "pulsar_vm_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.pulsar_vm.email}"
}

resource "google_compute_instance" "pulsar" {
  name         = "${var.entorno}-vm"
  machine_type = var.machine_type
  zone         = local.zone
  tags         = ["pulsar"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = var.disk_size_gb
      type  = "pd-balanced"
    }
  }

  network_interface {
    network    = "default"
    subnetwork = data.google_compute_subnetwork.default.self_link

    access_config {
      # IP externa efímera — SOLO para administración/debug manual (ver
      # var.admin_source_ranges en network.tf). El tráfico real de
      # producción/consumo de Pulsar desde Cloud Run usa la IP interna
      # (ver output "ip_privada" y gestion-de-trabajos/infra/service.tf).
    }
  }

  service_account {
    email  = google_service_account.pulsar_vm.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = local.startup_script

  allow_stopping_for_update = true

  depends_on = [google_project_service.apis]
}
