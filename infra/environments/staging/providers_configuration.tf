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
