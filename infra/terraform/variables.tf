variable "project_id" {
  description = "Progetto Google Cloud dell'ambiente (es. wearx-staging)."
  type        = string
}

variable "environment" {
  description = "staging oppure production."
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment deve essere staging o production."
  }
}

variable "region" {
  description = "Regione Google Cloud. europe-west1 (Belgio): UE e vicina a Supabase (Irlanda)."
  type        = string
  default     = "europe-west1"
}

variable "deploy_claim" {
  description = <<-EOT
    Chi può fare il deploy dal repository giaqufra-cyber/WearX (scritto per esteso in iam.tf,
    così i controlli automatici lo vedono), cioè la parte finale del "sub" del token GitHub:
    staging "environment:staging", produzione "environment:production" (gli ambienti di
    GitHub: production chiede l'approvazione, staging accetta solo il ramo main).
  EOT
  type        = string
  validation {
    condition     = contains(["environment:staging", "environment:production"], var.deploy_claim)
    error_message = "deploy_claim: environment:staging oppure environment:production."
  }
}

variable "alert_email" {
  description = "Email che riceve gli allarmi (servizio giù, errori, budget)."
  type        = string
}

variable "billing_account" {
  description = "Account di fatturazione per l'avviso di budget (vuoto = nessun budget)."
  type        = string
  default     = ""
}

variable "monthly_budget_eur" {
  description = "Budget mensile: avvisi al 50%, 90% e 100% (anche previsto)."
  type        = number
  default     = 40
}

variable "cloudflare_account_id" {
  description = "Account Cloudflare (R2). Non è un segreto."
  type        = string
}

variable "api_min_instances" {
  description = "Istanze dell'API sempre pronte (0 = si spegne quando non usata, primo accesso più lento)."
  type        = number
  default     = 0
}

variable "api_max_instances" {
  type    = number
  default = 4
}

variable "supabase_url" {
  type    = string
  default = "https://alcpqfphwygpktrcyauu.supabase.co"
}

variable "storage_access_key" {
  description = "Access key id del token S3 di R2 (non segreto; il secret è in Secret Manager)."
  type        = string
  default     = ""
}

variable "min_app_version" {
  type    = string
  default = "0.1.0"
}

variable "attestation_mode" {
  description = "off / soft / required (seduta 22). In produzione almeno soft."
  type        = string
  default     = "soft"
}

variable "apple_team_id" {
  type    = string
  default = ""
}

variable "play_integrity_project_number" {
  type    = string
  default = ""
}

variable "ios_store_url" {
  type    = string
  default = ""
}

variable "android_store_url" {
  type    = string
  default = ""
}

variable "push_provider" {
  description = "expo in produzione; log finché non c'è il progetto EAS."
  type        = string
  default     = "log"
}

variable "sentry_traces_sample_rate" {
  type    = number
  default = 0.05
}
