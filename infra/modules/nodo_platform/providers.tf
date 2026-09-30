variable "enable_intervals" {
  description = "Enlaza OAuth sólo después de aprobación externa y versiones explícitas de secretos."
  type        = bool
  default     = false
}

variable "enable_web_push" {
  type    = bool
  default = false
}

variable "provider_secret_versions" {
  description = "IDs lógicos => versión numérica Secret Manager. Ningún valor ni alias latest."
  type        = map(string)
  default     = {}
  validation {
    condition     = alltrue([for version in values(var.provider_secret_versions) : can(regex("^[1-9][0-9]*$", version))])
    error_message = "Los secretos de proveedor requieren versiones numéricas explícitas."
  }
}

variable "public_app_url" {
  description = "Origen HTTPS canónico PWA usado para OAuth, BFF, correo y Web Push."
  type        = string
  default     = ""
  validation {
    condition     = var.public_app_url == "" || can(regex("^https://[A-Za-z0-9.-]+(:443)?$", var.public_app_url))
    error_message = "public_app_url debe ser un origen HTTPS sin path ni credenciales."
  }
}

variable "web_push_public_key" {
  description = "Clave pública VAPID; no es la clave privada."
  type        = string
  default     = ""
}

variable "web_push_contact" {
  description = "Sujeto VAPID aprobado mailto: o https:."
  type        = string
  default     = ""
}

variable "enable_vertex_ai" {
  description = "Habilita API/IAM mínimo Vertex sólo tras aprobar modelo, ubicación, tarifas y gasto."
  type        = bool
  default     = false
}

variable "ai_configuration" {
  type = object({
    model                  = optional(string, "")
    location               = optional(string, "")
    user_monthly_requests  = optional(number, 200)
    org_monthly_requests   = optional(number, 2000)
    user_monthly_tokens    = optional(number, 1000000)
    org_monthly_tokens     = optional(number, 10000000)
    user_monthly_usd       = optional(number, 0)
    org_monthly_usd        = optional(number, 0)
    input_usd_per_million  = optional(number, 0)
    output_usd_per_million = optional(number, 0)
  })
  default = {}
  validation {
    condition = alltrue([
      for value in [var.ai_configuration.user_monthly_requests, var.ai_configuration.org_monthly_requests,
      var.ai_configuration.user_monthly_tokens, var.ai_configuration.org_monthly_tokens] : value >= 1 && floor(value) == value
      ]) && alltrue([
      for value in [var.ai_configuration.user_monthly_usd, var.ai_configuration.org_monthly_usd,
      var.ai_configuration.input_usd_per_million, var.ai_configuration.output_usd_per_million] : value >= 0
    ])
    error_message = "Límites de solicitudes/tokens positivos enteros y límites de costo no negativos."
  }
}

locals {
  intervals_api_secret_ids = var.enable_intervals ? {
    INTERVALS_CLIENT_ID           = "intervals-client-id"
    INTERVALS_CLIENT_SECRET       = "intervals-client-secret"
    INTERVALS_WEBHOOK_SECRET      = "intervals-webhook-secret"
    PROVIDER_TOKEN_ENCRYPTION_KEY = "provider-token-encryption-key"
  } : {}
  push_secret_ids = var.enable_web_push ? {
    WEB_PUSH_PRIVATE_KEY = "web-push-private-key"
    PUSH_ENCRYPTION_KEY  = "push-encryption-key"
  } : {}
  api_provider_secrets = {
    for name, id in merge(local.intervals_api_secret_ids, local.push_secret_ids) : name => {
      secret_id = id
      version   = lookup(var.provider_secret_versions, id, "")
    }
  }
  worker_provider_secrets = {
    for name, id in merge(var.enable_intervals ? { PROVIDER_TOKEN_ENCRYPTION_KEY = "provider-token-encryption-key" } : {}, local.push_secret_ids) : name => {
      secret_id = id
      version   = lookup(var.provider_secret_versions, id, "")
    }
  }
  api_runtime_secrets    = merge(var.api_secret_bindings, local.api_provider_secrets)
  worker_runtime_secrets = merge(var.worker_secret_bindings, local.worker_provider_secrets)
  # object_store currently uses one private bucket with owner-scoped fit/export prefixes.
  storage_env = {
    STORAGE_BACKEND     = "gcs"
    STORAGE_BUCKET      = google_storage_bucket.fit.name
    DATA_RETENTION_DAYS = tostring(var.fit_retention_days)
    PRIVACY_GCS_BUCKETS = join(",", [google_storage_bucket.fit.name, google_storage_bucket.exports.name])
  }
  provider_env = {
    PUBLIC_APP_URL          = var.public_app_url
    INTERVALS_REDIRECT_URI  = var.enable_intervals ? "${var.public_app_url}/athlete/connections/intervals/callback" : ""
    INTERVALS_BACKFILL_DAYS = "90"
    INTERVALS_PUSH_WORKOUTS = "false"
    WEB_PUSH_PUBLIC_KEY     = var.enable_web_push ? var.web_push_public_key : ""
    WEB_PUSH_CONTACT        = var.enable_web_push ? var.web_push_contact : ""
  }
  ai_env = {
    AI_PROVIDER                = var.enable_vertex_ai ? "vertex" : "simulated"
    AI_GCP_PROJECT             = var.project_id
    AI_GCP_LOCATION            = var.ai_configuration.location
    AI_MODEL                   = var.ai_configuration.model
    AI_USER_MONTHLY_REQUESTS   = tostring(var.ai_configuration.user_monthly_requests)
    AI_ORG_MONTHLY_REQUESTS    = tostring(var.ai_configuration.org_monthly_requests)
    AI_USER_MONTHLY_TOKENS     = tostring(var.ai_configuration.user_monthly_tokens)
    AI_ORG_MONTHLY_TOKENS      = tostring(var.ai_configuration.org_monthly_tokens)
    AI_USER_MONTHLY_BUDGET_USD = tostring(var.ai_configuration.user_monthly_usd)
    AI_ORG_MONTHLY_BUDGET_USD  = tostring(var.ai_configuration.org_monthly_usd)
    AI_INPUT_USD_PER_MILLION   = tostring(var.ai_configuration.input_usd_per_million)
    AI_OUTPUT_USD_PER_MILLION  = tostring(var.ai_configuration.output_usd_per_million)
  }
  api_runtime_env    = merge(var.api_env, local.provider_env, local.ai_env, local.storage_env, { ENVIRONMENT = var.environment })
  worker_runtime_env = merge(var.worker_env, local.provider_env, local.storage_env, { ENVIRONMENT = var.environment })
}

resource "google_project_iam_custom_role" "vertex_prompt" {
  count       = var.enable_vertex_ai ? 1 : 0
  project     = var.project_id
  role_id     = "${replace(local.resource_prefix, "-", "_")}_vertex_prompt"
  title       = "NODO ${var.environment} prompt inference"
  description = "Sólo inferencia, sin administración, tuning ni acceso a datasets."
  permissions = ["aiplatform.endpoints.predict"]
}

resource "google_project_iam_member" "api_vertex_prompt" {
  count      = var.enable_vertex_ai ? 1 : 0
  project    = var.project_id
  role       = google_project_iam_custom_role.vertex_prompt[0].name
  member     = "serviceAccount:${google_service_account.api.email}"
  depends_on = [google_project_service.required]
}

resource "terraform_data" "runtime_contract" {
  lifecycle {
    precondition {
      condition     = !var.deploy_workloads || var.public_app_url != ""
      error_message = "Workloads requieren public_app_url HTTPS canónico."
    }
    precondition {
      condition = alltrue([for binding in values(merge(local.api_provider_secrets, local.worker_provider_secrets)) :
      contains(var.managed_secret_ids, binding.secret_id) && can(regex("^[1-9][0-9]*$", binding.version))])
      error_message = "Cada proveedor habilitado requiere un contenedor administrado y versión numérica explícita."
    }
    precondition {
      condition = alltrue(flatten([for bindings in values(local.secret_bindings_by_service) : [
        for binding in values(bindings) : contains(var.managed_secret_ids, binding.secret_id) && can(regex("^[1-9][0-9]*$", binding.version))
      ]]))
      error_message = "Todas las referencias de secretos requieren contenedores declarados y versiones numéricas, nunca latest."
    }
    precondition {
      condition = !var.deploy_workloads || (contains(keys(local.api_runtime_secrets), "DATABASE_URL") &&
        contains(keys(var.migration_secret_bindings), "DATABASE_URL") &&
      (!var.enable_worker || contains(keys(local.worker_runtime_secrets), "DATABASE_URL")))
      error_message = "API/migración y worker habilitado necesitan su binding DATABASE_URL."
    }
    precondition {
      condition = length(setintersection(toset(keys(var.pwa_secret_bindings)), toset([
        "DATABASE_URL", "INTERVALS_CLIENT_SECRET", "INTERVALS_WEBHOOK_SECRET", "PROVIDER_TOKEN_ENCRYPTION_KEY",
        "WEB_PUSH_PRIVATE_KEY", "PUSH_ENCRYPTION_KEY", "RESEND_API_KEY", "EMAIL_QUEUE_KEY", "AI_API_KEY"
      ]))) == 0
      error_message = "Secretos de datos/proveedores pertenecen a API/worker y no se enlazan a la PWA."
    }
    precondition {
      condition     = !var.enable_web_push || (var.web_push_public_key != "" && can(regex("^(mailto:|https://)", var.web_push_contact)))
      error_message = "Web Push requiere clave pública VAPID y sujeto aprobado."
    }
    precondition {
      condition = !var.enable_vertex_ai || (var.ai_configuration.model != "" && var.ai_configuration.location != "" &&
        var.ai_configuration.user_monthly_usd > 0 && var.ai_configuration.org_monthly_usd > 0 &&
      var.ai_configuration.input_usd_per_million > 0 && var.ai_configuration.output_usd_per_million > 0)
      error_message = "Vertex requiere modelo/ubicación explícitos y límites/tarifas aprobados positivos."
    }
    precondition {
      condition = (length(setintersection(toset(keys(local.api_runtime_env)), toset(keys(local.api_runtime_secrets)))) == 0 &&
      length(setintersection(toset(keys(local.worker_runtime_env)), toset(keys(local.worker_runtime_secrets)))) == 0)
      error_message = "Una ENV no puede definirse simultáneamente como pública y como secreto."
    }
  }
}
