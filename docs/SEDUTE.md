# WearX: piano di lavoro in 25 sedute

Riferimento: specifica tecnica v0.1 (documento "WearX — Specifica tecnica e architettura v0.1").
Ogni seduta chiude con codice testato e salvato. Le sedute che richiedono un'azione del
fondatore (account, pagamenti, documenti legali) lo dicono nella colonna "Serve da te".

| # | Seduta | Risultato verificabile | Serve da te |
|---|--------|------------------------|-------------|
| 1 | Fondamenta | Monorepo, design token, API con /v1/config, schema DB completo con RLS, app con 4 tab che legge gli stili, CI | Repository GitHub vuoto |
| 2 | Autenticazione backend | Verifica JWT Supabase, /v1/me, nickname-check, onboarding/profile, limiti di frequenza Redis | Progetto Supabase (UE) |
| 3 | Design system app | Button, Chip, Input, Toggle, Toast, Skeleton, Sheet + test dei componenti (jest-expo) | — |
| 4 | Registrazione nell'app | Splash, form di registrazione con validazione (età < 16 bloccata), OTP, login | — |
| 5 | Verifica dell'età | Astrazione fornitore + fornitore finto per i test, webhook firmato, schermate verifica / tipo profilo / stili | Scelta del fornitore (D5) |
| 6 | Stili (backend) | Ricerca trigram, pagina stile, adesioni, regole di età sugli stili | — |
| 7 | Stili (app) | Esplora con ricerca, pagina stile, Aderisci | — |
| 8 | Pipeline delle foto | URL firmati, quarantena, worker Arq: EXIF, varianti WebP, blurhash, hash | — |
| 9 | Post (backend) | Creazione, modifica, eliminazione, capi, link; suite di test di autorizzazione (IDOR) | — |
| 10 | Nuovo fit (app) | Galleria multi-selezione, ordine del carosello, capi, didascalia, upload con ripresa | — |
| 11 | Voti | Voto anonimo (HMAC), post_stats nella stessa transazione, conferma stile, test di concorrenza | — |
| 12 | Feed (backend) | Punteggio R, Redis per stile, cursore di sessione, quote di esplorazione, ripiego senza Redis | — |
| 13 | Feed (app) | Card, carosello, tag sulla foto, slider del voto, aggiornamento ottimistico | — |
| 14 | Portfolio | Griglia, riordino (indice frazionario), copertina, capsule | — |
| 15 | Account privati | Follow con richiesta, blocchi, regole di visibilità 16-17 / 18+ | — |
| 16 | Moderazione (backend) | Segnalazioni con priorità, moderation_actions, interfacce classificatore e hash | Accesso al servizio di hash matching |
| 17 | Admin web | Next.js: stili, coda di moderazione, utenti, log di audit | — |
| 18 | Notifiche ed eventi | Push (Expo), lista in-app, raccolta eventi con lista consentita | — |
| 19 | Insight | Aggregazione notturna, API, schermata Insight con soglie minime | — |
| 20 | Privacy e sicurezza (app) | Dispositivi collegati, export dati, cancellazione con 30 giorni, impostazioni | — |
| 21 | Business e link negozi | Account Business, controllo dei link, redirect, click | — |
| 22 | Hardening | Attestazione dispositivo, anti-abuso voti, Semgrep, scansione ZAP | — |
| 23 | Infrastruttura | Terraform, deploy staging, segreti, osservabilità | Account cloud e Expo |
| 24 | Qualità | Test E2E Maestro, test di carico k6, audit accessibilità, testi completi | — |
| 25 | Beta | Build EAS, TestFlight e Play test interno, runbook | Account Apple (99 $/anno) e Google Play (25 $) |

## Registro

### Seduta 1 — 2026-10-04

Fatto:
- Monorepo pnpm + Turborepo: `apps/mobile`, `services/api`, `packages/design-tokens`.
- Design token dal prototipo (colori, caratteri, raggi, spaziature, fasce del voto) con test.
- Archivo "Expanded" (larghezza 125%, pesi 800 e 900) ricavato dal font variabile ufficiale OFL.
- API FastAPI: errori RFC 9457, `X-Request-Id`, controllo versione minima (426), `/healthz`,
  `/readyz`, `GET /v1/config`.
- Database: schema completo della specifica (20 tabelle) nello schema `app`, RLS ovunque,
  ruolo `wearx_api` con permessi minimi, log di audit non modificabile, 12 stili iniziali.
- App Expo SDK 57 + Expo Router: 4 tab come nel prototipo, tema scuro, font, feed ed Esplora
  che leggono gli stili dall'API.
- CI GitHub Actions: lint, tipi, test con Postgres e Redis veri, bundle Android, gitleaks, pip-audit.

Verifiche: 25 test API passati; ruff, mypy strict, tsc puliti; bundle Android compilato;
schermate controllate in anteprima web a 390x844.

Scelte prese in questa seduta (rispetto alla specifica):
- Tabelle nello schema `app` e non `public`: Supabase non le espone mai via PostgREST.
- Aggiunti `profiles.adult_on`, `styles.sort_order`; vincoli "Business solo 18+" e
  "minori con adult_on" direttamente nel database.
- Corretto un errore della specifica: il controllo del nickname su `citext` con `~` ignorava le
  maiuscole; ora il check è su `nickname::text`.
- Decisioni aperte D1–D7: applicate le proposte della specifica (in attesa di conferma).

Da fare in seduta 2: autenticazione (serve il progetto Supabase), profilo, limiti di frequenza.
