# Staging: si aggiorna da solo a ogni modifica su main. Valori pubblici (nessun segreto).
project_id            = "wearx-staging"
environment           = "staging"
deploy_claim          = "environment:staging"
alert_email           = "DA_IMPOSTARE" # la tua email per gli allarmi
cloudflare_account_id = "DA_IMPOSTARE"
api_min_instances     = 0
monthly_budget_eur    = 25
attestation_mode      = "soft"
push_provider         = "log"
