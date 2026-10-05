# ---------- Cloud Run ----------
# Le immagini le aggiorna la pipeline di deploy (gcloud): Terraform non le tocca dopo il primo
# avvio (ignore_changes), così i due non si contendono la versione in esercizio.

resource "google_cloud_run_v2_service" "api" {
  name                = "${local.prefix}-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.environment == "production"

  template {
    service_account                  = google_service_account.run["api"].email
    max_instance_request_concurrency = 40
    timeout                          = "30s"

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    containers {
      image = local.placeholder.service

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      dynamic "env" {
        for_each = local.api_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.secret_env["api"]
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app[env.value].secret_id
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        http_get {
          path = "/readyz"
        }
        period_seconds    = 3
        timeout_seconds   = 3
        failure_threshold = 20
      }

      liveness_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds    = 30
        timeout_seconds   = 3
        failure_threshold = 3
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.readers, google_secret_manager_secret_version.placeholder]
}

resource "google_cloud_run_v2_service" "admin" {
  name                = "${local.prefix}-admin"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.environment == "production"

  template {
    service_account = google_service_account.run["admin"].email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = local.placeholder.service

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_project_service.apis]
}

# API e pannello sono pubblici (l'accesso lo controlla l'app con i token di Supabase).
resource "google_cloud_run_v2_service_iam_member" "public" {
  for_each = {
    api   = google_cloud_run_v2_service.api.name
    admin = google_cloud_run_v2_service.admin.name
  }
  location = var.region
  name     = each.value
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------- Worker (sempre accesi, senza porte in ascolto) ----------

resource "google_cloud_run_v2_worker_pool" "worker" {
  name                = "${local.prefix}-worker"
  location            = var.region
  deletion_protection = var.environment == "production"

  scaling {
    manual_instance_count = 1
  }

  template {
    service_account = google_service_account.run["worker"].email

    containers {
      image   = local.placeholder.worker
      command = ["arq"]
      args    = ["app.worker.WorkerSettings"]

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi" # foto da elaborare ed export dei dati
        }
      }

      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.secret_env["worker"]
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.readers, google_secret_manager_secret_version.placeholder]
}

# Worker che visita i siti esterni: identità senza alcun ruolo, solo database, Redis, Safe
# Browsing e Sentry. Nessun accesso a chiavi dell'archivio, di Supabase o dei push.
resource "google_cloud_run_v2_worker_pool" "linkcheck" {
  name                = "${local.prefix}-linkcheck"
  location            = var.region
  deletion_protection = var.environment == "production"

  scaling {
    manual_instance_count = 1
  }

  template {
    service_account = google_service_account.run["linkcheck"].email

    containers {
      image   = local.placeholder.worker
      command = ["arq"]
      args    = ["app.worker.LinkCheckSettings"]

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      dynamic "env" {
        for_each = local.linkcheck_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.secret_env["linkcheck"]
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.readers, google_secret_manager_secret_version.placeholder]
}

# ---------- Migrazioni (job lanciato dalla pipeline prima di ogni deploy) ----------

resource "google_cloud_run_v2_job" "migrate" {
  name                = "${local.prefix}-migrate"
  location            = var.region
  deletion_protection = var.environment == "production"

  template {
    task_count = 1

    template {
      service_account = google_service_account.run["migrate"].email
      timeout         = "600s"
      max_retries     = 0

      containers {
        image   = local.placeholder.job
        command = ["alembic"]
        args    = ["upgrade", "head"]

        dynamic "env" {
          for_each = local.secret_env["migrate"]
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.app[env.value].secret_id
                version = "latest"
              }
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.readers, google_secret_manager_secret_version.placeholder]
}
