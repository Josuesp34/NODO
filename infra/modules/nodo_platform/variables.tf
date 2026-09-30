variable "project_id" {
  description = "ID del proyecto GCP dedicado al entorno."
  type        = string
}

variable "environment" {
  description = "Entorno aislado de NODO."
  type        = string

  validation {
    condition     = contains(["staging", "prod"], var.environment)
    error_message = "environment debe ser staging o prod."
  }
}

variable "region" {
  description = "Región común para Cloud Run, Cloud SQL, Storage y Artifact Registry."
  type        = string
}

variable "name_prefix" {
  description = "Prefijo corto de recursos."
  type        = string
  default     = "nodo"
}

variable "labels" {
  description = "Etiquetas adicionales; no incluir datos personales."
  type        = map(string)
  default     = {}
}

variable "network_cidr" {
  description = "CIDR privado para egreso directo de Cloud Run."
  type        = string
  default     = "10.20.0.0/24"
}

variable "private_service_prefix_length" {
  description = "Prefijo reservado para Private Service Access de Cloud SQL."
  type        = number
  default     = 16
}

variable "database_name" {
  description = "Nombre lógico de la base."
  type        = string
  default     = "nodo"
}

variable "database_tier" {
  description = "Tier de Cloud SQL confirmado con la calculadora antes del apply."
  type        = string
}

variable "database_disk_size_gb" {
  description = "Disco inicial de Cloud SQL; crece automáticamente."
  type        = number
  default     = 20
}

variable "database_backup_retained_count" {
  description = "Número de copias automáticas retenidas."
  type        = number
  default     = 14
}

variable "deletion_protection" {
  description = "Protección contra borrado accidental para datos y workloads."
  type        = bool
  default     = true
}

variable "bucket_name_prefix" {
  description = "Prefijo globalmente único elegido por el operador; no es un project ID."
  type        = string
}

variable "fit_retention_days" {
  description = "Retención de archivos FIT, sujeta a la política de privacidad aprobada."
  type        = number
  default     = 365
}

variable "export_retention_days" {
  description = "Retención de exportaciones solicitadas por usuarios."
  type        = number
  default     = 30
}

variable "logical_backup_retention_days" {
  description = "Retención de exportaciones lógicas para recuperación."
  type        = number
  default     = 30
}

variable "deploy_workloads" {
  description = "Crea Cloud Run sólo después de publicar imágenes por digest y cargar secretos."
  type        = bool
  default     = false
}

variable "enable_worker" {
  description = "Crea el worker pool cuando app.worker esté implementado y probado."
  type        = bool
  default     = false
}

variable "api_image" {
  description = "Imagen API inmutable, con @sha256."
  type        = string
  default     = ""

  validation {
    condition     = var.api_image == "" || can(regex("@sha256:[0-9a-f]{64}$", var.api_image))
    error_message = "api_image debe estar vacía o fijada por digest sha256."
  }
}

variable "pwa_image" {
  description = "Imagen PWA inmutable, con @sha256."
  type        = string
  default     = ""

  validation {
    condition     = var.pwa_image == "" || can(regex("@sha256:[0-9a-f]{64}$", var.pwa_image))
    error_message = "pwa_image debe estar vacía o fijada por digest sha256."
  }
}

variable "api_container_port" {
  type    = number
  default = 8080
}

variable "pwa_container_port" {
  type    = number
  default = 8080
}

variable "api_min_instances" {
  type    = number
  default = 0
}

variable "api_max_instances" {
  type    = number
  default = 4
}

variable "pwa_min_instances" {
  type    = number
  default = 0
}

variable "pwa_max_instances" {
  type    = number
  default = 4
}

variable "worker_instances" {
  description = "Worker pools usan escalado manual y generan costo mientras están activos."
  type        = number
  default     = 1
}

variable "worker_command" {
  type    = list(string)
  default = ["python"]
}

variable "worker_args" {
  type    = list(string)
  default = ["-m", "app.services.jobs"]
}

variable "migration_command" {
  type    = list(string)
  default = ["alembic"]
}

variable "migration_args" {
  type    = list(string)
  default = ["-c", "alembic.ini", "upgrade", "head"]
}

variable "api_env" {
  description = "Variables no secretas de la API."
  type        = map(string)
  default     = {}
}

variable "pwa_env" {
  description = "Variables no secretas de la PWA."
  type        = map(string)
  default     = {}
}

variable "worker_env" {
  description = "Variables no secretas del worker."
  type        = map(string)
  default     = {}
}

variable "managed_secret_ids" {
  description = "Contenedores Secret Manager; los valores se cargan fuera de Terraform."
  type        = set(string)
  default = [
    "database-url",
    "session-signing-key",
    "provider-token-encryption-key",
    "intervals-client-id",
    "intervals-client-secret",
    "intervals-webhook-secret",
    "ai-api-key",
    "resend-api-key",
    "email-queue-key",
    "smtp-username",
    "smtp-password",
  ]
}

variable "api_secret_bindings" {
  description = "ENV => {secret_id, version}; sólo IDs/versiones, nunca valores."
  type = map(object({
    secret_id = string
    version   = string
  }))
  default = {}
}

variable "pwa_secret_bindings" {
  description = "Secretos mínimos del BFF/PWA."
  type = map(object({
    secret_id = string
    version   = string
  }))
  default = {}
}

variable "worker_secret_bindings" {
  description = "Secretos mínimos del worker."
  type = map(object({
    secret_id = string
    version   = string
  }))
  default = {}
}

variable "migration_secret_bindings" {
  description = "Secretos mínimos del job de migración."
  type = map(object({
    secret_id = string
    version   = string
  }))
  default = {}
}

variable "api_allow_unauthenticated" {
  description = "Debe permanecer false cuando el BFF sea la frontera pública."
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "Repositorio owner/name autorizado para WIF."
  type        = string
}

variable "github_deploy_refs" {
  description = "Refs exactas autorizadas a obtener identidad de despliegue."
  type        = set(string)
  default     = ["refs/heads/dev", "refs/heads/main"]
}

variable "artifact_reader_members" {
  description = "Lectores adicionales del registro, por ejemplo runtime/deploy de prod al promover desde staging."
  type        = set(string)
  default     = []
}

variable "billing_account_id" {
  description = "Cuenta de facturación confirmada. Null mantiene el budget sin crear."
  type        = string
  default     = null
  nullable    = true
}

variable "monthly_budget_units" {
  description = "Presupuesto mensual bruto confirmado, en unidades enteras de currency_code."
  type        = number
  default     = null
  nullable    = true
}

variable "budget_currency_code" {
  type    = string
  default = "USD"
}

variable "budget_thresholds" {
  type    = set(number)
  default = [0.25, 0.50, 0.75, 0.90, 1.00]
}

variable "monitoring_notification_channel_ids" {
  description = "Canales existentes y aprobados; vacía crea políticas sin notificaciones."
  type        = list(string)
  default     = []
}

variable "enable_monitoring_alerts" {
  description = "Activa políticas básicas sólo después de confirmar canales y umbrales con operación."
  type        = bool
  default     = false
}

variable "cloud_run_5xx_count_threshold" {
  description = "Número de respuestas 5xx por ventana de cinco minutos que dispara la alerta."
  type        = number
  default     = 5
}

variable "database_disk_utilization_threshold" {
  description = "Fracción de utilización de disco de Cloud SQL que dispara la alerta."
  type        = number
  default     = 0.80
}
