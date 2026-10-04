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

### Seduta 2 — 2026-10-04

Fatto:
- Verifica dei token Supabase (`app/auth.py`): solo ES256/RS256 dal JWKS, cache 10 minuti come
  indica la documentazione Supabase, ricarica per `kid` sconosciuto al massimo una volta al minuto,
  emittente, audience, scadenza e `sub` obbligatori, utenti anonimi rifiutati.
- Limiti di frequenza su Redis (`app/ratelimit.py`): finestra scorrevole con script Lua atomico,
  429 con `Retry-After`; se Redis è giù la richiesta passa e si registra un avviso.
- Endpoint: `POST /v1/auth/nickname-check` (20/min per IP), `POST /v1/onboarding/profile`
  (crea profilo + stili scelti, richiede verifica età superata e accettazione termini),
  `GET /v1/me`, `PATCH /v1/me` (bio, nascondi prezzi, nascondi numero voti, tipo account).
- Regole sui testi (`app/text_policy.py`): nickname riservati e frammenti vietati (wearx, admin,
  support, staff, official…, anche mascherati con punti), bio senza caratteri invisibili o di
  inversione del testo, massimo 150 caratteri e 4 righe.
- Migrazione 0003: tabella `age_verifications` (solo esito, mai immagini o date di nascita),
  `profiles.terms_version` e `terms_accepted_at` come prova del consenso.
- `packages/api-types`: tipi TypeScript generati dall'OpenAPI; la CI fallisce se non sono
  allineati all'API. Client dell'app esteso con chiamate autenticate e chiave di idempotenza.

Verifiche: 89 test API passati (64 nuovi). Coperti: token scaduti, emittente o audience sbagliati,
`alg: none`, HS256 firmato con la chiave pubblica, chiave simmetrica nel JWKS, firma di un'altra
chiave, payload manomesso, `kid` sconosciuti a raffica, registrazioni simultanee con lo stesso
nickname, minorenni su stili 18+ e Business, campi del profilo non modificabili, Redis spento.
ruff, mypy strict, tsc puliti; export OpenAPI stabile; bundle Android compilato.

Scelte e differenze rispetto alla specifica:
- `PATCH /v1/me` invece di `PUT`: l'aggiornamento è parziale.
- L'account Business resta dietro il flag `business_accounts` (spento fino alla Fase 2).
- Log su stderr invece che stdout.

Da fare in seduta 3: design system dell'app (componenti + test con jest-expo).
Serve da te prima della seduta 4: progetto Supabase gratuito in regione Francoforte.

### Seduta 3 — 2026-10-04

Fatto:
- Codice su GitHub: `giaqufra-cyber/WearX`, ramo `main` (sedute 1 e 2 caricate a inizio seduta).
- Test dell'app con jest-expo + React Native Testing Library v14, impostati come da
  documentazione Expo SDK 57; aggiunti alla CI.
- Design system in `apps/mobile/src/ui/` (import unico da `@/ui`): Button (5 varianti, 3 misure,
  caricamento senza cambiare larghezza), IconButton, Chip, TextField (prefisso, errore annunciato,
  mostra/nascondi password), PasswordStrength, Toggle, Checkbox, SegmentedControl, Toast con
  provider globale, Skeleton (fermo se "riduci movimento" è attivo), Sheet, EmptyState, Badge,
  StyleTile. Tutti con ruoli e stati ARIA e aree toccabili ≥ 44 pt.
- `src/lib/validation.ts`: nickname, robustezza password, età da data di nascita (date
  inesistenti e 29 febbraio gestiti), allineati alle regole del server.
- Catalogo dei componenti su `/dev/ui`, solo in sviluppo (in produzione rimanda alla home).
  Screenshot: `docs/screens/seduta-03-design-system.png`.

Verifiche: 39 test app (23 di validazione, 16 sui componenti) + 89 test API, tutti passati;
tsc pulito; bundle Android compilato; catalogo controllato a schermo a 390x844.
I test hanno trovato due difetti veri di accessibilità (indicatore password e avviso a comparsa
non leggibili da VoiceOver/TalkBack): corretti. Il controllo a schermo ne ha trovati tre di
impaginazione (selettore piccolo, pulsante in caricamento, etichetta tagliata): corretti.

Note tecniche:
- TypeScript 6 non include più i tipi globali per default: `types: ["jest", "node"]` nel tsconfig.
- RNTL v14: render ed eventi sono asincroni (`await`), i timer finti vanno fatti avanzare in `act`.

Da fare in seduta 4: schermate di registrazione e login collegate a Supabase.
Serve da te prima della seduta 4: progetto Supabase gratuito in regione Francoforte.
