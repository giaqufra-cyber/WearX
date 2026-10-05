# Produzione: deploy solo a mano, con approvazione (ambiente "production" su GitHub).
# NB: l'API in produzione parte solo con il fornitore vero di verifica dell'età (decisione D5).
project_id            = "wearx-production"
environment           = "production"
deploy_claim          = "environment:production"
alert_email           = "DA_IMPOSTARE" # la tua email per gli allarmi
cloudflare_account_id = "DA_IMPOSTARE"
api_min_instances     = 1
monthly_budget_eur    = 60
attestation_mode      = "soft"
push_provider         = "expo"
