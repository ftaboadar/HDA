terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }
}

locals {
  # account_id de Service Account tiene un límite de 30 caracteres en GCP
  # (^[a-z](?:[-a-z0-9]{4,28}[a-z0-9])$) — encontrado corriendo
  # `terraform plan` de verdad (no lo atrapa `validate`) contra
  # mocks-pagos/infra: "mocks-pagos-poc-mock-mercadopago" tiene 32. Se
  # trunca a 30 y se quita un "-" colgante si la truncación cae justo
  # después de uno (el regex no permite terminar en "-").
  account_id_sin_guion_final = trimsuffix(substr("${var.entorno}-${var.service_name}", 0, 30), "-")
}

resource "google_service_account" "this" {
  account_id   = local.account_id_sin_guion_final
  display_name = "Runtime de ${var.service_name} (${var.entorno})"
}

resource "google_cloud_run_v2_service" "this" {
  name     = "${var.entorno}-${var.service_name}"
  location = var.region
  labels   = var.labels

  template {
    service_account = google_service_account.this.email

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = 2var.max_instance_count
    }

    max_instance_request_concurrency = var.max_instance_request_concurrency

    dynamic "vpc_access" {
      # Direct VPC egress — ver variables.tf, vpc_network. Sin esto, el
      # tráfico saliente de este servicio NUNCA se origina desde la VPC
      # del proyecto, así que un firewall restringido al rango de la VPC
      # (en vez de 0.0.0.0/0) simplemente no lo dejaría pasar.
      for_each = var.vpc_network == null ? [] : [1]
      content {
        egress = var.vpc_egress
        network_interfaces {
          network    = var.vpc_network
          subnetwork = var.vpc_subnetwork
        }
      }
    }

    containers {
      image   = var.image
      command = var.command
      args    = var.args

      ports {
        container_port = var.container_port
      }

      resources {
        startup_cpu_boost = var.startup_cpu_boost
        cpu_idle          = var.cpu_idle
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.value.name
          value = env.value.secret_id == null ? env.value.value : null

          dynamic "value_source" {
            for_each = env.value.secret_id == null ? [] : [1]
            content {
              secret_key_ref {
                secret  = env.value.secret_id
                version = coalesce(env.value.secret_version, "latest")
              }
            }
          }
        }
      }

      dynamic "volume_mounts" {
        for_each = var.enable_cloudsql ? [1] : []
        content {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
    }

    dynamic "volumes" {
      for_each = var.enable_cloudsql ? [1] : []
      content {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [var.cloudsql_connection_name]
        }
      }
    }
  }
}

# El propio runtime necesita permiso para conectarse a Cloud SQL vía el
# Cloud SQL Auth Proxy embebido de Cloud Run (mismo rol que
# proveedores/infra/iam.tf otorga a su SA de runtime).
resource "google_project_iam_member" "cloudsql_client" {
  count   = var.enable_cloudsql ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.this.email}"
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.public_access ? 1 : 0
  name     = google_cloud_run_v2_service.this.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers" # PoC — ver mismo criterio en proveedores/infra/cloudrun.tf
}
