data "google_project" "this" {}

locals {
  prefix = "wearx-${var.environment}"
  # Indirizzi deterministici di Cloud Run (https://<servizio>-<numero progetto>.<regione>.run.app):
  # servono nelle variabili d'ambiente senza creare dipendenze circolari.
  api_url   = "https://${local.prefix}-api-${data.google_project.this.number}.${var.region}.run.app"
  admin_url = "https://${local.prefix}-admin-${data.google_project.this.number}.${var.region}.run.app"

  # Immagini segnaposto per il primo avvio: le immagini vere le mette la pipeline di deploy.
  placeholder = {
    service = "us-docker.pkg.dev/cloudrun/container/hello"
    worker  = "us-docker.pkg.dev/cloudrun/container/worker-pool"
    job     = "us-docker.pkg.dev/cloudrun/container/job"
  }

  # Identità dei servizi: ognuna riceve SOLO i segreti che usa.
  identities = {
    api       = "API pubblica"
    worker    = "Worker in background"
    linkcheck = "Worker che visita i link ai negozi (nessun permesso)"
    admin     = "Pannello dello staff"
    migrate   = "Migrazioni del database"
  }

  # segreto => variabile d'ambiente e chi può leggerlo.
  secrets = {
    "database-url"           = { env = "WEARX_DATABASE_URL", readers = ["api", "worker", "linkcheck"] }
    "migration-database-url" = { env = "WEARX_MIGRATION_DATABASE_URL", readers = ["migrate"] }
    "redis-url"              = { env = "WEARX_REDIS_URL", readers = ["api", "worker", "linkcheck"] }
    "vote-pepper"            = { env = "WEARX_VOTE_PEPPER", readers = ["api", "worker"] }
    "age-webhook-secret"     = { env = "WEARX_AGE_WEBHOOK_SECRET", readers = ["api"] }
    "storage-secret-key"     = { env = "WEARX_STORAGE_SECRET_KEY", readers = ["api", "worker"] }
    "supabase-secret-key"    = { env = "WEARX_SUPABASE_SECRET_KEY", readers = ["worker"] }
    "expo-access-token"      = { env = "WEARX_EXPO_ACCESS_TOKEN", readers = ["worker"] }
    "safe-browsing-key"      = { env = "WEARX_SAFE_BROWSING_KEY", readers = ["linkcheck"] }
    "sentry-dsn"             = { env = "WEARX_SENTRY_DSN", readers = ["api", "worker", "linkcheck"] }
  }

  secret_readers = merge([
    for name, s in local.secrets : {
      for reader in s.readers : "${name}/${reader}" => { secret = name, reader = reader }
    }
  ]...)

  secret_env = {
    for who in keys(local.identities) : who => {
      for name, s in local.secrets : s.env => name if contains(s.readers, who)
    }
  }

  # Configurazione non segreta, comune a API e worker (i valori vuoti non si passano).
  common_env = { for k, v in {
    WEARX_ENV                       = var.environment
    WEARX_GCP_PROJECT               = var.project_id
    WEARX_SUPABASE_URL              = var.supabase_url
    WEARX_PUBLIC_API_URL            = local.api_url
    WEARX_STORAGE_ENDPOINT_URL      = "https://${var.cloudflare_account_id}.eu.r2.cloudflarestorage.com"
    WEARX_STORAGE_REGION            = "auto"
    WEARX_STORAGE_BUCKET            = cloudflare_r2_bucket.media.name
    WEARX_STORAGE_ACCESS_KEY        = var.storage_access_key
    WEARX_PUSH_PROVIDER             = var.push_provider
    WEARX_SENTRY_TRACES_SAMPLE_RATE = tostring(var.sentry_traces_sample_rate)
    WEARX_GOOGLE_METADATA_AUTH      = "true"
    # Posti nel pool di Supabase (modalità session): vedi docs/INFRA.md, "Capacità".
    WEARX_DB_POOL_SIZE    = "2"
    WEARX_DB_MAX_OVERFLOW = "2"
  } : k => v if v != "" }

  api_env = merge(local.common_env, { for k, v in {
    WEARX_PROXY_MODE                    = "google"
    WEARX_ADMIN_ORIGINS                 = jsonencode([local.admin_url])
    WEARX_MIN_APP_VERSION               = var.min_app_version
    WEARX_ATTESTATION_MODE              = var.attestation_mode
    WEARX_APP_ATTEST_ALLOW_DEVELOPMENT  = var.environment == "production" ? "false" : "true"
    WEARX_APPLE_TEAM_ID                 = var.apple_team_id
    WEARX_PLAY_INTEGRITY_PROJECT_NUMBER = var.play_integrity_project_number
    WEARX_IOS_STORE_URL                 = var.ios_store_url
    WEARX_ANDROID_STORE_URL             = var.android_store_url
    WEARX_DB_POOL_SIZE                  = "3"
    WEARX_DB_MAX_OVERFLOW               = "2"
  } : k => v if v != "" })

  # Il worker dei link riceve il minimo indispensabile.
  linkcheck_env = { for k, v in local.common_env : k => v if contains(
    ["WEARX_ENV", "WEARX_GCP_PROJECT", "WEARX_SENTRY_TRACES_SAMPLE_RATE"], k
  ) }

  apis = [
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "playintegrity.googleapis.com",
    "run.googleapis.com",
    "safebrowsing.googleapis.com",
    "secretmanager.googleapis.com",
    "sts.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------- Immagini ----------

resource "google_artifact_registry_repository" "images" {
  #checkov:skip=CKV_GCP_84:Immagini senza segreti: basta la cifratura gestita da Google (chiavi proprie = costi e gestione in più)
  location      = var.region
  repository_id = "wearx"
  format        = "DOCKER"
  description   = "Immagini di API, worker e pannello"

  # Si tengono le ultime 15 versioni; le altre spariscono da sole dopo 30 giorni.
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "tieni-le-ultime"
    action = "KEEP"
    most_recent_versions {
      keep_count = 15
    }
  }
  cleanup_policies {
    id     = "via-le-vecchie"
    action = "DELETE"
    condition {
      older_than = "2592000s"
    }
  }

  depends_on = [google_project_service.apis]
}

# ---------- Foto (Cloudflare R2, giurisdizione UE) ----------

resource "cloudflare_r2_bucket" "media" {
  account_id   = var.cloudflare_account_id
  name         = "${local.prefix}-media"
  jurisdiction = "eu"
  location     = "weur"
}
