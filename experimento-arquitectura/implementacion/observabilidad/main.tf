# Observabilidad transversal a los 3 microservicios nuevos + Proveedores —
# Cloud Monitoring/Cloud Trace/Cloud Logging ya recolectan métricas y logs
# de Cloud Run SIN ningún agente ni configuración adicional (request
# count, latencias, uso de CPU/memoria, todo bajo el prefijo de métrica
# run.googleapis.com/*) — lo que este stack agrega es (a) las APIs
# explícitas que la tarea pide habilitar y (b) una capa de visualización
# real (Grafana) con un dashboard de ejemplo ya provisto, en vez de dejar
# todo detrás de la consola nativa de GCP.
#
# HALLAZGO (experto-gcp): "Google Managed Service for Prometheus" (GMP) no
# tiene una API propia distinta de monitoring.googleapis.com — se activa
# habilitando esa misma API; el componente adicional de GMP es un
# COLECTOR (self-deployed u operado) que hace scraping de endpoints
# Prometheus nativos. Ninguno de los 3 microservicios nuevos ni Proveedores
# expone un endpoint /metrics Prometheus propio hoy (todos son FastAPI
# simple, sin instrumentación `prometheus_client`) — así que desplegar un
# colector GMP en este momento no tendría nada real que scrapear más allá
# de lo que Cloud Monitoring YA recibe nativamente de Cloud Run. Por eso
# este stack se limita a habilitar la API (cumple el pedido literal) y
# documenta esto como ruta de mejora futura, en vez de desplegar un
# colector GMP sin datos que recolectar.

terraform {
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
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}
