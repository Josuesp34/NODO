variable "queue_oldest_pending_seconds" {
  description = "Tiempo máximo de espera vencida, excluyendo run_after futuro."
  type        = number
  default     = 300
}

locals {
  operational_log_alerts = {
    jobs_dead = {
      title  = "Trabajos en dead letter"
      filter = "jsonPayload.event=\"worker_health\" AND jsonPayload.dead_count>0"
    }
    queue_stalled = {
      title  = "Cola vencida o lease obsoleto"
      filter = "jsonPayload.event=\"worker_health\" AND (jsonPayload.oldest_pending_age_seconds>${var.queue_oldest_pending_seconds} OR jsonPayload.stale_running_count>0)"
    }
    email_failed = {
      title  = "Entrega de correo fallida"
      filter = "jsonPayload.event=\"job_failed\" AND jsonPayload.kind=\"send_resend_email\""
    }
    provider_failed = {
      title  = "Proveedor o Web Push fallido"
      filter = "jsonPayload.event=\"job_failed\" AND (jsonPayload.kind=\"intervals_sync\" OR jsonPayload.kind=\"intervals_disconnect\" OR jsonPayload.kind=\"send_web_push\" OR jsonPayload.kind=\"product_notification\")"
    }
    backup_failed = {
      title = "Copia de seguridad requiere atención"
      # Native failed operations plus the read-only backup inventory checker.
      filter = "(protoPayload.serviceName=\"sqladmin.googleapis.com\" AND protoPayload.methodName=~\"(?i)backup\" AND protoPayload.status.code>0) OR (jsonPayload.event=\"backup_check\" AND jsonPayload.healthy=false)"
    }
  }
}

resource "google_monitoring_alert_policy" "operational_logs" {
  for_each = var.enable_monitoring_alerts ? local.operational_log_alerts : {}

  project               = var.project_id
  display_name          = "NODO ${var.environment}: ${each.value.title}"
  combiner              = "OR"
  enabled               = true
  notification_channels = var.monitoring_notification_channel_ids
  user_labels           = local.labels

  conditions {
    display_name = each.value.title
    condition_matched_log {
      filter = each.value.filter
      # No arbitrary payloads/IDs/emails/citations copied into alert labels.
    }
  }
  alert_strategy {
    notification_rate_limit {
      period = "1800s"
    }
    auto_close = "86400s"
  }
  documentation {
    content   = "Seguir docs/RUNBOOK_PRODUCCION.md. Consultar /admin/operations con cuenta autorizada. No copiar cuerpos, destinatarios, tokens o datos de atletas. Una política validada no acredita canal ni señal entregada."
    mime_type = "text/markdown"
  }
  depends_on = [google_project_service.required]
}

resource "google_logging_metric" "worker_heartbeat" {
  count       = var.enable_monitoring_alerts && var.enable_worker ? 1 : 0
  project     = var.project_id
  name        = "${local.resource_prefix}-worker-heartbeat"
  description = "Heartbeat agregado de NODO cada 60 segundos, sin payloads o identificadores de usuarios."
  filter      = "jsonPayload.event=\"worker_health\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
  depends_on = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "worker_heartbeat_absent" {
  count                 = var.enable_monitoring_alerts && var.enable_worker ? 1 : 0
  project               = var.project_id
  display_name          = "NODO ${var.environment}: heartbeat worker ausente"
  combiner              = "OR"
  enabled               = true
  notification_channels = var.monitoring_notification_channel_ids
  user_labels           = local.labels
  conditions {
    display_name = "Sin heartbeat durante cinco minutos"
    condition_absent {
      filter   = "resource.type=\"cloud_run_worker_pool\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.worker_heartbeat[0].name}\""
      duration = "300s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.worker_pool_name", "resource.label.location"]
      }
    }
  }
  documentation {
    content   = "Verificar worker pool y /admin/operations; reiniciar únicamente con autorización. Confirmar primero un heartbeat real: ausencia no detecta una serie que jamás existió. Validar parada/arranque sintéticos y recepción del canal antes de GO."
    mime_type = "text/markdown"
  }
}
