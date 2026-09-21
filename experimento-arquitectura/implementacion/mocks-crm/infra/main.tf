terraform {
  # State remoto en GCS, un bucket por proyecto y un prefix por stack: lo inicializan
  # scripts/comun.sh (tf_init) o, a mano:
  #   terraform init -backend-config="bucket=<PROYECTO>-tfstate" -backend-config="prefix=<stack>"
  # CI valida con `terraform init -backend=false`. Ver CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md §6.
  backend "gcs" {}

  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}
