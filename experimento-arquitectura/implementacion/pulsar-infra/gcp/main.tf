# Equivalente GCP del cluster local de Apache Pulsar (../docker-compose.yml).
# No existe un servicio gestionado de Pulsar en GCP (a diferencia de
# Pub/Sub) — ver ../README.md, sección final "Ver también". Este stack
# reproduce el mismo cluster de un solo nodo (Zookeeper + BookKeeper +
# Broker, 1 réplica de cada uno, igual que local) sobre UNA VM de Compute
# Engine corriendo el mismo docker-compose.yml ya validado, en vez de un
# despliegue GKE con el chart de ../helm/ (ese es "el siguiente paso" que
# el propio README ya dejaba pendiente — fuera de alcance de este PoC:
# más complejo, más caro, y el chart de Helm no se validó localmente
# todavía, así que llevarlo a GKE ahora sería una migración doble sin
# haber confirmado la primera).

terraform {
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
    "compute.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}
