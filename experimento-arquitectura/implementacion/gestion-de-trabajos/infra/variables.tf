variable "project_id" {
  description = "ID del proyecto de GCP"
  type        = string
}

variable "region" {
  description = "Región de GCP — southamerica-east1 (São Paulo) por defecto, igual que proveedores/infra/variables.tf"
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

    Con la sobresuscripción resuelta (15/15/15) y el cold-start del
    autoscaler resuelto (min_instance_count=10, ver service.tf), la corrida
    de ESC-01 llegó a 100% de aceptación / 0% de fallo con ESTE tier
    (db-custom-2-7680) -- p95 5646ms, la mejor corrida real hasta ahora
    (2026-09-17, ver k6/results/esc-01-summary-min-instances-fix.json).
    Cloud SQL quedó al 99.5% de CPU sostenido durante el pico en esa
    corrida.

    SE PROBÓ subir a `db-custom-4-15360` (4 vCPU/15GB, doble de cómputo)
    esperando aliviar ese 99.5% de CPU -- **empeoró de forma reproducible**
    en 2 corridas independientes (p95 7352ms y 7521ms, 3.7-4.6% de fallo,
    miles de "no available instance" en los logs de Cloud Run, ver
    k6/results/esc-01-summary-tier4-fix.json y RESULTADOS-ESCALABILIDAD-GCP.md
    sección "Anomalía sin resolver"). Se descartaron 2 hipótesis: (1) ruido
    de reinicio de la instancia -- descartado corriendo de nuevo con la
    instancia estable 20+ min; (2) pools de conexión stale en las instancias
    de Cloud Run que llevaban corriendo desde antes del cambio de tier --
    descartado forzando un redeploy completo (instancias 100% nuevas, pools
    frescos) y el resultado siguió siendo peor (p95 8612ms). La causa real
    de por qué el tier más grande rinde peor queda SIN CONFIRMAR -- revertido
    a `db-custom-2-7680` (la config con mejor resultado medido) en vez de
    seguir gastando corridas reales para adivinar. Pendiente para quien
    retome esto con más tiempo: instrumentar latencia interna del código
    (no solo métricas de infra) para aislar la causa.
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

variable "crm_mock_url" {
  description = "Output \"mock_crm_url\" del stack mocks-crm/infra — destino del Throttler de DISP-02"
  type        = string
  default     = "http://localhost:9200"
}

variable "crm_limite_rps" {
  description = <<-EOT
    Tasa (req/s) que el token bucket del Throttler respeta hacia el CRM, POR
    INSTANCIA de este servicio: el throttler vive en memoria de cada réplica.
    Con N instancias activas, la tasa agregada hacia el CRM es N veces este
    valor — el CRM responde 429 por el exceso y el throttler lo reintenta con
    backoff. 20 = mismo valor que docker-compose.disp02.yml (1 réplica local).
  EOT
  type        = string
  default     = "20"
}

variable "max_instance_count" {
  description = <<-EOT
    Tope de instancias de Cloud Run. 20 es la configuración con la que el
    equipo corrió ESC-01. Con cpu = "2", el total es max × 2 vCPU y debe
    caber en la cuota de CPU de Cloud Run del proyecto: un proyecto nuevo
    trae 20 vCPU por servicio, así que ahí el máximo posible es 10.
  EOT
  type        = number
  default     = 20
}

variable "min_instance_count" {
  description = <<-EOT
    Default 1 en hogaralpes: la config real de ESC-01 (10 instancias × 2
    vCPU = 20 vCPU) agota sola la cuota de CPU/región del proyecto (20
    vCPU), sin dejar nada para Proveedores/mocks-crm/Grafana (min>0 en esos).
    Pasar -var min_instance_count=10 solo durante una corrida real de
    ESC-01, y volver a 1 (o menos) después -- son instancias facturando
    de forma continua, no bajo demanda.
  EOT
  type        = number
  default     = 1
}

variable "log_detalle" {
  description = "\"completo\" (default) emite los logs de trazado fino por request (http_request_completada, comando_*, mensaje_publicado...). \"minimo\" los apaga: usarlo en una corrida real de ESC-01, donde un log extra por request cuesta CPU y dinero en Cloud Logging."
  type        = string
  default     = "completo"
}
