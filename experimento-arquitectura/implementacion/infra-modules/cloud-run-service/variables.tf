# Módulo reusable: un servicio de Cloud Run v2 + su propia Service
# Account + (opcionalmente) el enganche a una instancia de Cloud SQL ya
# existente. Extrae el patrón repetido en
# proveedores/infra/cloudrun.tf + proveedores/infra/iam.tf para los 3 servicios
# nuevos (reputacion, gestion-de-trabajos, mocks-pagos) sin forzarlos a
# compartir un solo archivo gigante como hace Proveedores (ahí tenía sentido
# por ser un solo experimento con api+worker+mocks fuertemente acoplados;
# aquí son 3 microservicios independientes con su propio ciclo de vida).

variable "project_id" {
  description = "ID del proyecto de GCP"
  type        = string
}

variable "region" {
  description = "Región de Cloud Run"
  type        = string
}

variable "entorno" {
  description = "Prefijo corto del entorno (ej. \"disp03-poc\", \"reputacion-poc\") — se antepone a todos los nombres de recursos que crea este módulo"
  type        = string
}

variable "service_name" {
  description = "Nombre corto del servicio dentro del entorno (ej. \"api\", \"consumidor\") — el nombre final del recurso Cloud Run es \"$${entorno}-$${service_name}\""
  type        = string
}

variable "image" {
  description = "Referencia completa de la imagen del contenedor (Artifact Registry o, para imágenes públicas como grafana/grafana, Docker Hub)"
  type        = string
}

variable "command" {
  description = "Entrypoint del contenedor"
  type        = list(string)
  default     = null
}

variable "args" {
  description = "Argumentos del entrypoint"
  type        = list(string)
  default     = null
}

variable "container_port" {
  description = "Puerto en el que escucha el contenedor (Cloud Run v2 default 8080; algunos servicios de este proyecto usan otro, ej. los mocks de pagos exponen 8000 — ver su Dockerfile)"
  type        = number
  default     = 8080
}

variable "env_vars" {
  description = <<-EOT
    Lista de variables de entorno. Cada elemento admite DOS formas
    mutuamente excluyentes:
      - { name = "X", value = "texto plano" }
      - { name = "X", secret_id = google_secret_manager_secret.foo.secret_id, secret_version = "latest" }
    (secret_version es opcional, default "latest" — mismo patrón que
    DATABASE_URL en proveedores/infra/cloudrun.tf).
  EOT
  type = list(object({
    name           = string
    value          = optional(string)
    secret_id      = optional(string)
    secret_version = optional(string)
  }))
  default = []
}

variable "min_instance_count" {
  description = "Instancias mínimas calientes. 0 es válido para servicios sin escenario de calidad que exija evitar cold start (ver justificación extensa en proveedores/infra/cloudrun.tf antes de subir esto a 1+ sin razón)."
  type        = number
  default     = 0
}

variable "max_instance_count" {
  type    = number
  default = 2
}

variable "max_instance_request_concurrency" {
  type    = number
  default = 80
}

variable "startup_cpu_boost" {
  type    = bool
  default = true
}

variable "cpu" {
  description = <<-EOT
    vCPUs por instancia (string, formato que espera Cloud Run v2: "1", "2",
    "4"...). Default "1" -- mismo comportamiento que antes de que esta
    variable existiera (Cloud Run asigna 1 vCPU si no se especifica nada
    en `resources.limits`, sin que sea una decisión consciente). Subir
    esto importa cuando `max_instance_request_concurrency` > 1: con
    Python y un ThreadPoolExecutor sirviendo requests concurrentes, el
    GIL hace que solo un hilo ejecute bytecode a la vez -- con 1 sola
    vCPU, N hilos concurrentes compiten por ese único núcleo para
    cualquier trabajo real de CPU (parseo/validación/serialización), no
    solo para I/O. Ver gestion-de-trabajos/infra/service.tf para el caso
    real que motivó exponer esto (ESC-01, variación de latencia sin
    explicación aislada solo con métricas de infra).
  EOT
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memoria por instancia (formato Cloud Run v2, ej. \"512Mi\", \"1Gi\"). Default \"512Mi\" -- mismo default silencioso de Cloud Run que ya regía antes de esta variable."
  type        = string
  default     = "512Mi"
}

variable "cpu_idle" {
  description = <<-EOT
    true (default de Cloud Run): la CPU se limita fuera de la ventana de
    una request — correcto para servicios request-driven normales.
    false: CPU siempre asignada, incluso sin requests entrantes —
    NECESARIO para un contenedor que corre un loop de fondo (ej. un
    consumidor pull de una cola) en vez de solo responder HTTP. Ver nota
    en reputacion/infra sobre por qué el consumidor de Pulsar de este
    proyecto NO se despliega con este módulo a pesar de esta opción
    existir (el problema no es solo cpu_idle, es que Cloud Run exige que
    el contenedor escuche en container_port para pasar su startup probe,
    y ese consumidor no tiene servidor HTTP).
  EOT
  type        = bool
  default     = true
}

variable "enable_cloudsql" {
  description = <<-EOT
    true si este servicio necesita conectarse a Cloud SQL. Es una variable
    separada de `cloudsql_connection_name` (no basta con revisar si esa es
    null) porque cuando el caller pasa
    `google_sql_database_instance.foo.connection_name` de una instancia que
    se crea en el MISMO plan, ese valor es "known after apply" — Terraform
    no puede usar un valor así en `count`/`for_each` (error real,
    encontrado corriendo `terraform plan`, no solo `validate`, contra los 3
    servicios nuevos). Esta variable sí es estática en cualquier caller.
  EOT
  type        = bool
  default     = false
}

variable "cloudsql_connection_name" {
  description = "connection_name de una instancia de Cloud SQL ya existente (ej. google_sql_database_instance.foo.connection_name). Ignorado si enable_cloudsql es false."
  type        = string
  default     = null
}

variable "vpc_network" {
  description = <<-EOT
    Nombre de la red VPC para habilitar Direct VPC egress (sin costo de
    conector adicional — GA en Cloud Run v2). null desactiva esto: el
    servicio usa el egress serverless por defecto (IP de Google, NO la
    de la VPC del proyecto). Ponerlo solo si el servicio necesita
    alcanzar algo por IP interna/privada que un firewall restringido al
    rango de la VPC deba dejar pasar — ej. gestion-de-trabajos hablando
    con la VM de Pulsar. Ver pulsar-infra/gcp/README (o
    DESPLIEGUE-GCP-INTEGRAL.md) para la justificación completa de por
    qué "el rango de IPs de Cloud Run" no es una cosa filtrable en un
    firewall sin esto.
  EOT
  type        = string
  default     = null
}

variable "vpc_subnetwork" {
  description = "Subred para Direct VPC egress — requerido si vpc_network no es null"
  type        = string
  default     = null
}

variable "vpc_egress" {
  description = "PRIVATE_RANGES_ONLY (default, más barato: solo el tráfico a rangos RFC1918 se enruta por la VPC) o ALL_TRAFFIC"
  type        = string
  default     = "PRIVATE_RANGES_ONLY"
}

variable "public_access" {
  description = "true agrega roles/run.invoker para allUsers (PoC — ver mismo criterio ya documentado en proveedores/infra/cloudrun.tf y mocks.tf). false no agrega ningún invoker adicional: quien llame este módulo es responsable de otorgar roles/run.invoker a la identidad que corresponda (ej. la SA de push de Pub/Sub)."
  type        = bool
  default     = true
}

variable "labels" {
  type    = map(string)
  default = {}
}
