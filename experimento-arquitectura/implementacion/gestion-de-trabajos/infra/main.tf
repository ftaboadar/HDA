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
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
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
    "sqladmin.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

data "google_project" "actual" {}

# Subred "default" del proyecto en esta región — se usa para Direct VPC
# egress del servicio (ver service.tf) y para restringir el firewall de
# la VM de Pulsar (pulsar-infra/gcp) al tráfico que realmente sale de la
# VPC del proyecto, en vez de 0.0.0.0/0. Asume que el proyecto conserva
# la red "default" en modo automático (cierto en un proyecto de PoC
# recién creado como hda-projectt) — si el equipo migra a una VPC
# custom, ajustar esta referencia.
data "google_compute_subnetwork" "default" {
  name    = "default"
  region  = var.region
  project = var.project_id
}
