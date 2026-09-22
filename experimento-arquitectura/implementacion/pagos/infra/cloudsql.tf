# Mismo patrón que proveedores/infra/cloudsql.tf — IP pública + red autorizada
# abierta, aceptable solo por ser un PoC (ver nota allá sobre alcance).

resource "google_sql_database_instance" "pagos" {
  name             = "${var.entorno}-pagos"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier = var.sql_tier

    ip_configuration {
      ipv4_enabled = true

      authorized_networks {
        name  = "abierto-solo-para-poc"
        value = "0.0.0.0/0"
      }
    }
  }

  deletion_protection = false
  depends_on          = [google_project_service.apis]
}

resource "google_sql_database" "pagos_db" {
  name     = "pagos"
  instance = google_sql_database_instance.pagos.name
}

resource "random_password" "db_password" {
  length  = 20
  special = false
}

resource "google_sql_user" "hda" {
  name     = "hda"
  instance = google_sql_database_instance.pagos.name
  password = random_password.db_password.result
  # Postgres no deja borrar un usuario que aún posee objetos (falla el `terraform destroy`).
  # ABANDON lo omite: al borrar la instancia, el usuario desaparece con ella.
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret" "db_url" {
  secret_id = "${var.entorno}-pagos-database-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_url" {
  secret      = google_secret_manager_secret.db_url.id
  secret_data = "postgresql+psycopg2://hda:${random_password.db_password.result}@/pagos?host=/cloudsql/${google_sql_database_instance.pagos.connection_name}"
}
