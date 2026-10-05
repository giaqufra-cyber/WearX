# ---------- Allarmi: servizio giù, worker fermi, errori del server, budget ----------

resource "google_monitoring_notification_channel" "email" {
  display_name = "WearX ${var.environment}: email"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
  depends_on = [google_project_service.apis]
}

locals {
  uptime_checks = {
    api     = { host = trimprefix(local.api_url, "https://"), path = "/readyz", what = "API (database e Redis)" }
    workers = { host = trimprefix(local.api_url, "https://"), path = "/healthz/workers", what = "worker in background" }
    admin   = { host = trimprefix(local.admin_url, "https://"), path = "/", what = "pannello dello staff" }
  }
}

resource "google_monitoring_uptime_check_config" "checks" {
  for_each     = local.uptime_checks
  display_name = "${local.prefix} ${each.key}"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = each.value.path
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = each.value.host
    }
  }
}

resource "google_monitoring_alert_policy" "uptime" {
  for_each     = local.uptime_checks
  display_name = "${local.prefix}: ${each.value.what} non risponde"
  combiner     = "OR"

  conditions {
    display_name = "Controllo ${each.key} fallito"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.checks[each.key].uptime_check_id}\" AND resource.type=\"uptime_url\""
      duration        = "600s"
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      aggregations {
        alignment_period     = "1200s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    content   = "Il controllo di ${each.value.path} fallisce da 10 minuti. Guida: docs/INFRA.md, sezione \"Se arriva un allarme\"."
    mime_type = "text/markdown"
  }
}

# Errori 5xx dell'API (dalla riga di log di ogni richiesta, senza dati personali).
resource "google_logging_metric" "api_5xx" {
  name   = "${local.prefix}-api-5xx"
  filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${google_cloud_run_v2_service.api.name}\" AND jsonPayload.logger=\"wearx.access\" AND jsonPayload.status>=500"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_alert_policy" "api_5xx" {
  display_name = "${local.prefix}: errori del server"
  combiner     = "OR"

  conditions {
    display_name = "Più di 5 errori 5xx in 5 minuti"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.api_5xx.name}\" AND resource.type=\"cloud_run_revision\""
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    content   = "L'API restituisce errori 5xx. Dettagli in Sentry e in Cloud Logging (cercare l'id della richiesta)."
    mime_type = "text/markdown"
  }
}

# Budget: avviso via email al 50% e al 90% della spesa e al 100% della spesa prevista.
resource "google_billing_budget" "monthly" {
  count           = var.billing_account == "" ? 0 : 1
  billing_account = var.billing_account
  display_name    = "${local.prefix} budget mensile"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = tostring(var.monthly_budget_eur)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.email.id]
    disable_default_iam_recipients   = false
  }

  depends_on = [google_project_service.apis]
}
