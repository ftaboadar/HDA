variable "project_id" {
  description = "ID del proyecto de GCP"
  type        = string
}

variable "region" {
  description = "Región de GCP — southamerica-east1 (São Paulo) por defecto, igual que DISP-03/infra/variables.tf"
  type        = string
  default     = "southamerica-east1"
}

variable "entorno" {
  description = "Prefijo corto para nombrar todos los recursos de este stack"
  type        = string
  default     = "gestion-trabajos-poc"
}

variable "sql_tier" {
  description = <<-EOT
    Tier de Cloud SQL — dimensionado para PoC académico, no para producción.
    Subido de db-custom-1-3840 a db-custom-2-7680 para el intento
    (fallido) de cerrar la brecha de ESC-01 (corridas 1 y 2, ver
    PENDIENTES-SESION.md sección 2) -- esa subida por sí sola NO ayudó
    porque `max_instance_request_concurrency`/`max_workers`/pool de
    conexiones (ver service.tf, app/api/main.py, app/common/config.py)
    quedaron desincronizados entre sí Y sobresuscritos contra
    `max_connections` real de Postgres, no por falta de memoria/CPU en el
    tier.

    Cálculo de `max_connections` (tabla oficial de Cloud SQL para Postgres,
    "Supported database flags" — depende de la memoria del tier, no es
    configurable directo salvo vía `database_flags`):
      - db-custom-1-3840 (3.75 GB) -> bucket "3.75 a <6 GB"  -> 100
      - db-custom-2-7680 (7.5 GB)  -> bucket "7.5 a <15 GB"  -> 400
    (cálculo por documentación pública, NO verificado empíricamente contra
    la instancia real vía `SHOW max_connections` — evitado a propósito en
    esta tarea para no tocar credenciales/Secret Manager).

    Con el tier actual (400), la config consistente elegida en service.tf
    (15 por instancia × max_instance_count=20 = 300, 75% de 400) deja
    margen razonable SIN subir de tier ni fijar `database_flags` manual.

    Recomendación CONDICIONAL (no aplicada acá): si una corrida de ESC-01
    con esta config consistente (15/15/15) sigue sin llegar a la tasa pico
    objetivo (1157 req/s, ver k6/esc-01.js) o sigue violando el p95 < 2s
    *por saturación real de Cloud SQL* (no por sobresuscripción, que ya
    quedó resuelta), el siguiente paso preferido es subir de tier otra vez
    (ej. db-custom-4-15360, 15GB -> bucket 500) y no manual
    `database_flags.max_connections` sobre el tier actual: subir de tier da
    más CPU/IOPS real (la app hace 2 escrituras síncronas por request, más
    el publish a Pulsar en el mismo executor -- un problema de cómputo, no
    solo de cantidad de conexiones) Y más `max_connections` "gratis" con el
    mismo margen de memoria que Google ya calculó, en vez de forzar un
    número de conexiones por encima del default sin saber cuánta memoria
    por conexión deja disponible ese tier. Managed Connection Pooling
    (Cloud SQL Enterprise Plus) o PgBouncer NO se recomiendan en esta
    escala: la demanda real (cientos de conexiones, no miles) todavía cabe
    cómodo en un tier más grande de Enterprise estándar, y esas opciones
    agregan costo de edición y complejidad operativa (Auth Proxy >=2.15.2,
    versión de mantenimiento mínima, reinicio para habilitar) que no se
    justifican todavía para un PoC de 2 meses.
  EOT
  type        = string
  default     = "db-custom-2-7680"
}

variable "pulsar_service_url" {
  description = <<-EOT
    URL del broker de Pulsar (pulsar://host:6650). Viene del output
    "ip_privada" del stack pulsar-infra/gcp (NO "ip_publica" — este
    servicio alcanza la VM por su IP interna vía Direct VPC egress, ver
    service.tf; la IP pública de la VM es solo para
    administración/debug manual desde fuera de la VPC). Ver
    ../../DESPLIEGUE-GCP-INTEGRAL.md para el orden de apply.
  EOT
  type        = string
  default     = "pulsar://localhost:6650"
}

variable "pulsar_topic_trabajos_finalizado" {
  type    = string
  default = "persistent://hda/gestion-trabajos/trabajos.finalizado"
}

variable "stripe_mock_url" {
  description = "Output \"uri\" del servicio mock-stripe del stack mocks-pagos/infra"
  type        = string
  default     = "http://localhost:9100"
}

variable "mercadopago_mock_url" {
  description = "Output \"uri\" del servicio mock-mercadopago del stack mocks-pagos/infra"
  type        = string
  default     = "http://localhost:9100"
}
