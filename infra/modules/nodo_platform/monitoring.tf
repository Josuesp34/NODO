data "google_project" "current" {
  project_id = var.project_id
}

resource "google_billing_budget" "monthly" {
  count = var.billing_account_id != null && var.monthly_budget_units != null ? 1 : 0

  billing_account = var.billing_account_id
  display_name    = "NODO ${var.environment} monthly guardrail"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency_code
      units         = tostring(var.monthly_budget_units)
    }
  }

  dynamic "threshold_rules" {
    for_each = var.budget_thresholds
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  all_updates_rule {
    monitoring_notification_channels = var.monitoring_notification_channel_ids
    disable_default_iam_recipients   = false
  }

  depends_on = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "cloud_run_5xx" {
  count = var.enable_monitoring_alerts ? 1 : 0

  project               = var.project_id
  display_name          = "NODO ${var.environment}: Cloud Run 5xx"
  combiner              = "OR"
  enabled               = true
  notification_channels = var.monitoring_notification_channel_ids

  conditions {
    display_name = "5xx durante cinco minutos"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.label.response_code_class = \"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.cloud_run_5xx_count_threshold
      duration        = "300s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  documentation {
    content   = "Ejecutar ops/smoke-production.sh y seguir docs/RUNBOOK_PRODUCCION.md. No incluir PII en la incidencia."
    mime_type = "text/markdown"
  }

  user_labels = local.labels

  depends_on = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "database_disk" {
  count = var.enable_monitoring_alerts ? 1 : 0

  project               = var.project_id
  display_name          = "NODO ${var.environment}: Cloud SQL disk utilization"
  combiner              = "OR"
  enabled               = true
  notification_channels = var.monitoring_notification_channel_ids

  conditions {
    display_name = "Disco de Cloud SQL por encima del umbral"
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND metric.type = \"cloudsql.googleapis.com/database/disk/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.database_disk_utilization_threshold
      duration        = "600s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  documentation {
    content   = "Revisar crecimiento y autoresize; no reducir disco. Seguir docs/RUNBOOK_PRODUCCION.md."
    mime_type = "text/markdown"
  }

  user_labels = local.labels

  depends_on = [google_project_service.required]
}
