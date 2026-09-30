variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "database_tier" {
  type = string
}

variable "bucket_name_prefix" {
  type = string
}

variable "github_repository" {
  type = string
}

variable "billing_account_id" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "monthly_budget_units" {
  type     = number
  default  = null
  nullable = true
}

variable "monitoring_notification_channel_ids" {
  type    = list(string)
  default = []
}

variable "enable_monitoring_alerts" {
  type    = bool
  default = false
}

variable "deploy_workloads" {
  type    = bool
  default = false
}

variable "enable_worker" {
  type    = bool
  default = false
}

variable "api_image" {
  type    = string
  default = ""
}

variable "pwa_image" {
  type    = string
  default = ""
}

variable "api_secret_bindings" {
  type = map(object({
    secret_id = string
    version   = string
  }))
  default = {}
}

variable "pwa_secret_bindings" {
  type = map(object({
    secret_id = string
    version   = string
  }))
  default = {}
}

variable "worker_secret_bindings" {
  type = map(object({
    secret_id = string
    version   = string
  }))
  default = {}
}

variable "migration_secret_bindings" {
  type = map(object({
    secret_id = string
    version   = string
  }))
  default = {}
}

variable "api_env" {
  description = "Variables de entorno no secretas del servicio."
  type        = map(string)
  default     = {}
}

variable "pwa_env" {
  description = "Variables de entorno no secretas del servicio."
  type        = map(string)
  default     = {}
}

variable "worker_env" {
  description = "Variables de entorno no secretas del servicio."
  type        = map(string)
  default     = {}
}

variable "artifact_reader_members" {
  description = "Lectores del registro, incluidos deployer y service agent de prod al promover desde staging."
  type        = set(string)
  default     = []
}
