# ---------- Identità dei servizi (account di servizio senza chiavi) ----------

resource "google_service_account" "run" {
  for_each     = local.identities
  account_id   = "${local.prefix}-${each.key}"
  display_name = "WearX ${var.environment}: ${each.value}"
}

# ---------- Segreti (Secret Manager) ----------
# Terraform crea solo i "contenitori" con un valore segnaposto: i valori veri li aggiunge a mano
# chi ha accesso (gcloud secrets versions add ...), e non passano mai da Terraform né da GitHub.

resource "google_secret_manager_secret" "app" {
  for_each  = local.secrets
  secret_id = "${local.prefix}-${each.key}"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "placeholder" {
  for_each    = local.secrets
  secret      = google_secret_manager_secret.app[each.key].id
  secret_data = "da-impostare"

  lifecycle {
    # Le versioni vere si aggiungono fuori da Terraform: questa resta solo come prima versione.
    ignore_changes = [secret_data, enabled]
  }
}

resource "google_secret_manager_secret_iam_member" "readers" {
  for_each  = local.secret_readers
  secret_id = google_secret_manager_secret.app[each.value.secret].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.run[each.value.reader].email}"
}

# ---------- Deploy da GitHub senza chiavi (Workload Identity Federation) ----------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "GitHub Actions (WearX)"
  attribute_mapping = {
    "google.subject"        = "assertion.sub"
    "attribute.repository"  = "assertion.repository"
    "attribute.ref"         = "assertion.ref"
    "attribute.environment" = "assertion.environment"
  }
  # Solo questo repository e solo i job dell'ambiente GitHub giusto (staging: solo ramo main;
  # production: con approvazione). Si confronta il "sub" del token.
  attribute_condition = "assertion.sub == 'repo:giaqufra-cyber/WearX:${var.deploy_claim}'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  account_id   = "${local.prefix}-deployer"
  display_name = "WearX ${var.environment}: deploy da GitHub Actions"
}

resource "google_service_account_iam_member" "deployer_wif" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/giaqufra-cyber/WearX"
}

# Il deploy aggiorna i servizi e carica le immagini; non legge i segreti.
resource "google_project_iam_member" "deployer" {
  for_each = toset(["roles/run.developer"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_push" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

# Per assegnare le identità ai servizi durante il deploy.
resource "google_service_account_iam_member" "deployer_act_as" {
  for_each           = google_service_account.run
  service_account_id = each.value.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
