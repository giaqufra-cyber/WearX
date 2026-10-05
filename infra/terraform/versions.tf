# Infrastruttura di WearX (seduta 23): Google Cloud (Cloud Run, Belgio) + Cloudflare R2 (UE).
# Un progetto Google per ambiente (staging, produzione): stesso codice, variabili diverse.
# Database e accessi restano su Supabase (Irlanda); Redis su Upstash (UE).
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.5"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.27"
    }
  }

  # Stato remoto in un bucket del progetto (creato a mano una volta: vedi docs/INFRA.md).
  # terraform init -backend-config=envs/<ambiente>.backend.hcl
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
  default_labels = {
    app         = "wearx"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Token Cloudflare (solo permesso "R2 Storage: Edit") nella variabile d'ambiente
# CLOUDFLARE_API_TOKEN: mai nei file.
provider "cloudflare" {}
