# WearX: accendere staging e produzione

Guida passo-passo (seduta 23). Tutto quello che è "infrastruttura" è scritto come codice in
`infra/terraform`. Questa guida dice cosa fare **una volta**, a mano, con i tuoi account.

> **Regola d'oro sui segreti.** Password, chiavi e token li incolli **tu**, dal tuo computer,
> direttamente nei servizi indicati (Secret Manager, Cloudflare, Upstash, Sentry). Non vanno mai
> in chat, nel repository, in GitHub o nei file `.tfvars`.

## Come è fatta

```
 telefono / pannello staff
          │ https
          ▼
 Cloud Run (Belgio, europe-west1)
  ├─ wearx-<env>-api        API pubblica            ──► Supabase Postgres + Auth (Irlanda)
  ├─ wearx-<env>-admin      pannello dello staff    ──► Upstash Redis (UE)
  ├─ wearx-<env>-worker     lavori in background    ──► Cloudflare R2 (foto, giurisdizione UE)
  ├─ wearx-<env>-linkcheck  visita i siti dei negozi (identità senza permessi, pochi segreti)
  └─ wearx-<env>-migrate    migrazioni del database (lanciate a ogni deploy)
 Secret Manager: i segreti, ognuno leggibile solo dai servizi che lo usano
 Monitoring: controlli ogni 5 minuti, allarmi via email, budget mensile
 Sentry (UE): errori dell'API, dei worker e (dalla seduta 25) crash dell'app
```

Due progetti Google separati: `wearx-staging` (prove, si aggiorna da solo a ogni modifica) e
`wearx-production` (solo a mano, con la tua approvazione su GitHub).

## Costi indicativi (ottobre 2026)

| Voce | Staging | Produzione |
|------|---------|------------|
| Cloud Run: API (0 istanze sempre pronte in staging, 1 in produzione) | ~0-2 $ | ~10 $ |
| Cloud Run: 2 worker sempre accesi | ~15 $ | ~15 $ |
| Upstash Redis (piano fisso 250 MB) | ~10 $ | ~10 $ |
| Cloudflare R2 (10 GB e traffico in uscita gratis) | 0 $ | 0 $ all'inizio |
| Sentry (piano gratuito), Supabase (piano gratuito), log e allarmi Google | 0 $ | 0 $ |

Il budget in Terraform manda un'email al 50% e al 90% della spesa e quando la spesa prevista
supera il 100% (25 € staging, 60 € produzione: si cambia in `envs/*.tfvars`).

## 1. Account (una volta)

1. **Google Cloud** — console.cloud.google.com: crea i progetti `wearx-staging` (e più avanti
   `wearx-production`), collega un account di fatturazione. Sul tuo computer installa
   [gcloud](https://cloud.google.com/sdk/docs/install) e [Terraform](https://developer.hashicorp.com/terraform/install),
   poi `gcloud auth login` e `gcloud auth application-default login`.
2. **Cloudflare** — account gratuito; attiva R2. Ti servono:
   - l'**Account ID** (pubblico): va in `cloudflare_account_id` di `envs/staging.tfvars`;
   - un **token API** con il solo permesso "R2 Storage: Edit", solo per Terraform: lo tieni sul
     tuo computer (`export CLOUDFLARE_API_TOKEN=...` prima di `terraform apply`);
   - dopo il primo `apply`: R2 → *Manage R2 API tokens* → token S3 "Object Read & Write" limitato
     al bucket `wearx-staging-media`. L'**Access Key ID** (pubblico) va in `storage_access_key`;
     il **Secret Access Key** va in Secret Manager (passo 3).
3. **Upstash** — console.upstash.com: database Redis in regione **eu-west-1 (Irlanda)**, piano
   fisso 250 MB (il worker interroga Redis di continuo: il piano a consumo costerebbe di più).
   Copia l'indirizzo `rediss://...` (con TLS): va in Secret Manager.
4. **Sentry** — sentry.io, regione dati **UE**. Progetto `wearx-api` (Python): il suo DSN va in
   Secret Manager. Il progetto `wearx-app` (React Native) serve dalla seduta 25.
5. **Supabase** — nel progetto esistente, SQL Editor, crea l'utente con cui parla l'API (scegli
   tu la password, non mandarmela):
   ```sql
   create role wearx_api_user login password '<password-lunga>' in role wearx_api;
   ```
   (Il ruolo `wearx_api` lo creano le migrazioni: esegui questo comando **dopo** il primo deploy,
   passo 5.) Connessione: *Connect → Session pooler* (IPv4, porta 5432), regione eu-west-1.

## 2. Terraform (una volta per ambiente)

```bash
cd infra/terraform
gcloud storage buckets create gs://wearx-staging-tfstate --project wearx-staging \
  --location europe-west1 --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://wearx-staging-tfstate --versioning
export CLOUDFLARE_API_TOKEN=...            # dal passo 1.2, solo in questo terminale
terraform init -backend-config=envs/staging.backend.hcl
terraform apply -var-file=envs/staging.tfvars
```

Il primo `apply` accende i servizi con immagini di prova di Google e segreti segnaposto: è
normale. Alla fine stampa gli indirizzi, il provider di Workload Identity e l'account di deploy.
Aggiungi `billing_account = "XXXXXX-XXXXXX-XXXXXX"` in `staging.tfvars` per attivare il budget.

## 3. Segreti (Secret Manager)

Per ognuno: `printf '%s' '<valore>' | gcloud secrets versions add <nome> --data-file=- --project wearx-staging`

| Segreto | Valore |
|---------|--------|
| `wearx-staging-database-url` | `postgresql+asyncpg://wearx_api_user.<ref>:<password>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres` |
| `wearx-staging-migration-database-url` | come sopra ma `postgresql+psycopg://postgres.<ref>:<password del database>@...` |
| `wearx-staging-redis-url` | `rediss://default:<token>@<nome>.upstash.io:6379` |
| `wearx-staging-vote-pepper` | `openssl rand -base64 48` (**mai cambiarlo dopo**: i voti si ritrovano con questo) |
| `wearx-staging-age-webhook-secret` | `openssl rand -base64 48` (staging: fornitore di prova) |
| `wearx-staging-storage-secret-key` | Secret Access Key di R2 (passo 1.2) |
| `wearx-staging-supabase-secret-key` | chiave `sb_secret_...` di Supabase |
| `wearx-staging-expo-access-token` | dalla seduta 25 (progetto Expo) |
| `wearx-staging-safe-browsing-key` | chiave API Google con solo "Safe Browsing API" abilitata |
| `wearx-staging-sentry-dsn` | DSN del progetto Sentry `wearx-api` |

I servizi leggono sempre l'ultima versione all'avvio: dopo aver cambiato un segreto basta un
nuovo deploy (o "Edit & deploy new revision" nella console).

## 4. GitHub

Settings → Environments:
- **staging**: *Deployment branches* = solo `main`.
- **production**: *Required reviewers* = tu; *Deployment branches* = solo `main`.

In ciascuno, variabili (non segreti) prese dall'output di Terraform: `GCP_PROJECT_ID`,
`GCP_REGION` (`europe-west1`), `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOYER`, `API_URL`,
`ADMIN_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` (la chiave publishable è pubblica).

## 5. Primo deploy e prova

Un push su `main` (o Actions → Deploy → *Run workflow*): costruisce le immagini, lancia le
migrazioni, aggiorna API, worker e pannello e controlla che tutto risponda. Poi:
- crea l'utente del database (passo 1.5) e aggiorna `wearx-staging-database-url`, nuovo deploy;
- `curl <API_URL>/readyz` → `{"status":"ok"}`; `curl <API_URL>/healthz/workers` → entrambi "ok";
- l'app punta allo staging con `EXPO_PUBLIC_API_URL=<API_URL>`;
- nel pannello: `<ADMIN_URL>` (accesso staff con secondo fattore).

**Controllo dell'IP reale** (serve ai limiti per IP): manda una richiesta con
`X-Forwarded-For: 1.2.3.4` a `/v1/auth/nickname-check` ripetuta oltre il limite: deve bloccare
il **tuo** IP, non 1.2.3.4 (l'API usa l'ultimo valore aggiunto da Google).

## 6. Produzione

Come staging con `envs/production.tfvars` e il progetto `wearx-production`, più: fornitore vero
di verifica dell'età (D5; con quello finto l'API di produzione non parte), SMTP, progetto Expo con
i push (`push_provider = "expo"`), `attestation_mode` e Team ID Apple (seduta 22). Il deploy si
lancia a mano: Actions → Deploy → `production`, poi approvi.

## Capacità (test di carico, seduta 24)

Un'istanza dell'API (1 vCPU) regge **200 persone attive in contemporanea** restando veloce (95%
delle risposte sotto 300 ms) e satura intorno a 120 richieste al secondo (`loadtest/README.md`).
Cloud Run aggiunge istanze da solo (fino a `api_max_instances`, 4): circa 800 persone attive
nello stesso momento, cioè decine di migliaia di persone al giorno.

**Pool di Supabase.** In modalità *session* ogni connessione aperta occupa un posto del pool del
progetto. Le connessioni massime sono: istanze API x 5 (3 + 2 di riserva) + worker x 4 +
migrazioni 1 = **25** con 4 istanze. Sul piano gratuito il pool parte da 15: in Supabase,
*Database → Settings → Connection pooling → Pool size*, mettilo a **30** (il piano gratuito
arriva a 60 connessioni). Se alzi `api_max_instances`, alza anche il pool (5 posti per istanza).

## Se arriva un allarme

- **"API non risponde"**: Cloud Run → `wearx-<env>-api` → *Logs*. Se `/readyz` dice
  `database: error` è Supabase (stato su status.supabase.com); `redis: error` è Upstash.
- **"worker in background non risponde"**: `/healthz/workers` dice quale; Cloud Run → *Worker
  pools* → log. Un riavvio: nuovo deploy o "Redeploy".
- **"errori del server"**: Sentry mostra l'errore con l'id della richiesta; lo stesso id si cerca
  in Cloud Logging (`jsonPayload.request_id="..."`).
- **Tornare alla versione prima**: Cloud Run → servizio → *Revisions* → manda il 100% del
  traffico alla revisione precedente (le migrazioni sono sempre compatibili all'indietro di
  una versione).
