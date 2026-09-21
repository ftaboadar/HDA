# VM de Compute Engine para correr k6 CONTRA GCP REAL sin pasar por la red
# doméstica de quien ejecuta la prueba — ver la explicación completa en
# ../README.md, sección "Por qué correr k6 desde una VM y no en local".
#
# Resumen del problema que resuelve: `esc-01.js` usa el executor
# `ramping-arrival-rate` con `maxVUs: 2000` (modelo abierto — sostiene la
# tasa objetivo, hasta 1157 req/s, sin importar cuánto tarden en responder
# las requests en vuelo). Con las latencias ya observadas contra GCP real
# (p95 ~10s, picos de hasta 60s bajo el escenario sin corregir), eso implica
# miles de conexiones TCP/TLS concurrentes salientes. Corrido desde una
# laptop en una red doméstica, esas conexiones saturan la tabla de
# NAT/conntrack (y la CPU) del router de consumo — tumba la conectividad de
# TODA la red, no solo la del propio k6. Una VM en la misma región que los
# servicios (southamerica-east1, igual que proveedores/infra, gestion-de-trabajos/
# infra y pulsar-infra/gcp) evita el problema por completo: la carga sale
# directo desde la red de Google hacia Cloud Run, sin tocar ningún router
# doméstico, y de paso da una medición más realista (sin la latencia/jitter
# de la conexión residencial del desarrollador metida en el resultado).

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
    "compute.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}
