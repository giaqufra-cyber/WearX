# WearX: piano di lavoro in 25 sedute

Riferimento: specifica tecnica v0.1 (documento "WearX — Specifica tecnica e architettura v0.1").
Ogni seduta chiude con codice testato e salvato. Le sedute che richiedono un'azione del
fondatore (account, pagamenti, documenti legali) lo dicono nella colonna "Serve da te".

| # | Seduta | Risultato verificabile | Serve da te |
|---|--------|------------------------|-------------|
| 1 | Fondamenta | Monorepo, design token, API con /v1/config, schema DB completo con RLS, app con 4 tab che legge gli stili, CI | Repository GitHub vuoto |
| 2 | Autenticazione backend | Verifica JWT Supabase, /v1/me, nickname-check, onboarding/profile, limiti di frequenza Redis | Progetto Supabase (UE) |
| 3 | Design system app | Button, Chip, Input, Toggle, Toast, Skeleton, Sheet + test dei componenti (jest-expo) | — |
| 4 | Registrazione nell'app | Splash, form di registrazione con validazione (età < 16 bloccata), OTP, login | Impostazioni Supabase (modello email con codice) |
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
| 22 | Hardening | Attestazione dispositivo, anti-abuso voti, media e numero dei voti sul proprio fit aggiornati ogni ora (deciso in seduta 19), Semgrep, scansione ZAP | — |
| 23 | Infrastruttura | Terraform, deploy staging, segreti, osservabilità | Account cloud e Expo |
| 24 | Qualità | Test E2E Maestro, test di carico k6, audit accessibilità, testi completi | — |
| 25 | Beta | Build EAS, TestFlight e Play test interno, runbook | Account Apple (99 $/anno) e Google Play (25 $) |

## Prima di far provare l'app ad altri (obbligatorio)

Promemoria fissi: senza questi punti l'app funziona solo per il fondatore.

- [ ] **Dominio** (circa 10 €/anno) e **servizio email** collegato a Supabase come SMTP
      personalizzato. Senza: Supabase manda al massimo 2 email all'ora e solo agli indirizzi
      del team del progetto.
- [ ] Con l'SMTP: modello "Confirm signup" con `{{ .Token }}` e `EXPO_PUBLIC_EMAIL_OTP=1`
      nell'app (conferma con codice a 6 cifre invece del link).
- [ ] Supabase → Redirect URLs: togliere `exp://**` (resta solo `wearx://**`).
- [ ] Fornitore vero di verifica dell'età (decisione D5) al posto di quello di prova, con il suo
      segreto per i webhook (`WEARX_AGE_WEBHOOK_SECRET`).
- [ ] **Moderazione** (seduta 16): richiedere l'accesso a un servizio di hash matching per
      materiale pedopornografico noto (Microsoft PhotoDNA o Thorn Safer: tempi non immediati),
      scegliere il classificatore delle foto (Rekognition, Vision SafeSearch o Hive, trattamento
      nell'UE), almeno un moderatore reperibile per i P0 (1 ora) più uno di riserva, procedura
      scritta con il legale per la segnalazione alla Polizia Postale e la conservazione delle prove.
- [ ] **Pannello staff** (seduta 17): pubblicarlo su un indirizzo proprio (es. `staff.` del
      dominio, Vercel o simile) e scriverlo in `WEARX_ADMIN_ORIGINS` dell'API; ogni persona dello
      staff entra con email, password e app di autenticazione (obbligatoria); almeno 2 admin.
- [ ] **Push** (seduta 18): progetto EAS (`extra.eas.projectId` in app.json, seduta 23), chiavi
      APNs (Apple) e FCM (Google) caricate su Expo, "sicurezza avanzata" dei push attiva nel
      progetto Expo con il suo token in `WEARX_EXPO_ACCESS_TOKEN` (segreto, solo sul server),
      `WEARX_PUSH_PROVIDER=expo`. Prova su un telefono vero con una build di sviluppo (Expo Go su
      Android non riceve più i push).
- [ ] **Account e password** (seduta 20): chiave segreta di Supabase solo nel secret manager del
      server (`WEARX_SUPABASE_SECRET_KEY`, serve a cancellare gli account dopo i 30 giorni: senza,
      la cancellazione definitiva aspetta); con l'SMTP, modello "Reset Password" con
      `{{ .Token }}` (codice a 6 cifre); in Redirect URLs resta `wearx://**` (serve al link di
      recupero quando non c'è il codice).
- [ ] **Link ai negozi** (seduta 21): chiave di Google Safe Browsing (gratuita, progetto Google
      Cloud) in `WEARX_SAFE_BROWSING_KEY`, solo sul server: senza, contano solo i domini bloccati
      dallo staff. Il worker che visita i link gira in una rete senza accesso ai servizi interni
      (seduta 23: difesa in più contro il "DNS rebinding", oltre al controllo degli indirizzi).
- [ ] **Verifica del dispositivo** (seduta 22): Team ID Apple in `WEARX_APPLE_TEAM_ID` (App
      Attest, serve l'account Apple della seduta 25); progetto Google Cloud collegato a Play
      Console con Play Integrity attiva, numero del progetto in
      `WEARX_PLAY_INTEGRITY_PROJECT_NUMBER` e account di servizio (JSON, SEGRETO, solo nel
      secret manager) in `WEARX_GOOGLE_SERVICE_ACCOUNT_JSON`; in produzione
      `WEARX_ATTESTATION_MODE=soft` (poi `required` quando la beta conferma che funziona) e
      `WEARX_APP_ATTEST_ALLOW_DEVELOPMENT=false`. Link agli store in `WEARX_IOS_STORE_URL` e
      `WEARX_ANDROID_STORE_URL` (schermata "Aggiorna WearX").
- [ ] **Infrastruttura** (seduta 23): seguire `docs/INFRA.md` — progetti Google Cloud
      `wearx-staging` e `wearx-production` con fatturazione, account Cloudflare (R2), Upstash
      Redis (UE), Sentry (regione UE), utente del database `wearx_api_user` su Supabase,
      `terraform apply`, segreti in Secret Manager, ambienti e variabili su GitHub. In
      `envs/*.tfvars`: la tua email per gli allarmi e l'Account ID di Cloudflare.

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
Serve da te prima della seduta 4: progetto Supabase gratuito in regione UE.

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
Serve da te prima della seduta 4: progetto Supabase gratuito in regione UE.

### Seduta 4 — 2026-10-04

Fatto:
- Progetto Supabase collegato: `https://alcpqfphwygpktrcyauu.supabase.co`, regione **West EU
  (Irlanda)**. Va bene per il GDPR (UE); la specifica diceva Francoforte: vale l'Irlanda.
  Le chiavi JWT del progetto sono ES256 pubblicate su JWKS: compatibili con la verifica dell'API.
- Nell'app c'è solo la chiave *publishable* (pubblica per definizione). `src/lib/env.ts` si
  rifiuta di partire se qualcuno ci mette una chiave `service_role`/`sb_secret_`.
- Sessione salvata cifrata (`src/lib/secureStorage.ts`): chiave AES-256 nuova a ogni scrittura nel
  portachiavi del telefono (Keychain/Keystore, solo questo dispositivo), testo cifrato in
  AsyncStorage. Rinnovo del token solo con l'app in primo piano.
- Navigazione protetta (`Stack.Protected`): un solo gruppo raggiungibile alla volta, deciso da
  `decideRoute` (sessione + `GET /v1/me`): `(auth)` → `(onboarding)` → `(tabs)`, più `offline`
  e `suspended`. Un indirizzo protetto aperto da fuori rimanda al benvenuto (verificato sul web).
- Schermate: benvenuto (come il prototipo), registrazione (nickname controllato dal vivo con
  pausa di battitura, email, password con robustezza + controllo violazioni Have I Been Pwned in
  k-anonymity, data di nascita con blocco sotto i 16 anni, due consensi), codice a 6 cifre con
  reinvio dopo 60 s, accesso, segnaposto della verifica età, offline con "Riprova", account sospeso.
  Pulsante "Esci" nel profilo. Screenshot: `docs/screens/seduta-04-accesso.png`.
- Privacy: la data di nascita resta solo in memoria (serve alla seduta 5) e non arriva a Supabase;
  il nickname va nei metadati solo come promemoria (il profilo nasce dopo la verifica dell'età).
  Se un'email è già registrata l'app non lo dice (niente enumerazione degli account).
- Registrazione col telefono pronta ma spenta (`EXPO_PUBLIC_PHONE_SIGNUP=1` per accenderla) finché
  non c'è un fornitore SMS.
- `services/api/.env.example`: `WEARX_SUPABASE_URL` del progetto.

Verifiche: 77 test app (+38: instradamento, modulo, k-anonymity, archivio cifrato, errori,
schermate con Supabase finto, nickname con pausa) + 89 test API; tsc pulito; bundle Android
compilato; schermate controllate a 390x844. Il controllo a schermo ha trovato un difetto del
TextField (non si restringeva sotto la sua larghezza naturale: giorno/mese/anno uscivano dallo
schermo): corretto con `minWidth: 0`.

Note tecniche:
- `Stack.Protected` con `redirectTo` esiste solo da SDK 58: qui si usa l'ordine dei gruppi +
  `unstable_settings.initialRouteName`.
- Il container di sviluppo non raggiunge supabase.co: la registrazione vera si prova sul telefono.
  Sul telefono l'API deve essere raggiungibile (`EXPO_PUBLIC_API_URL`), altrimenti dopo il codice
  compare la schermata "offline": è atteso finché l'API non è online (seduta 23).
- Da fare più avanti: recupero password (seduta 20), schermata "aggiorna l'app" per il 426 (seduta 22).

Aggiornamento dopo la prova sulla dashboard: senza SMTP personalizzato Supabase non permette di
modificare il modello dell'email (contiene solo il link) e consegna al massimo 2 email all'ora,
solo agli indirizzi del team del progetto. Quindi:
- Conferma email **con link** finché non c'è l'SMTP: il link conferma l'indirizzo e riapre l'app
  su `/verify?code=…`; l'app scambia il codice monouso con la sessione (flusso PKCE: il codice
  vale solo insieme al segreto rimasto sul telefono). Link scaduto/già usato e link aperto su un
  altro dispositivo hanno la loro schermata ("Email confermata, ora accedi").
- Il codice a 6 cifre resta pronto: si accende con `EXPO_PUBLIC_EMAIL_OTP=1` quando ci sarà l'SMTP.
- 86 test app (+9).

Serve da te (dashboard Supabase):
1. Authentication → URL Configuration → Redirect URLs: aggiungi `wearx://**` e, solo per lo
   sviluppo con Expo Go, `exp://**` (da togliere prima della beta).
2. Authentication → Sign In / Providers → Email: "Confirm email" attivo; password minima 10
   caratteri con minuscole, maiuscole, numeri e simboli.
3. Per le prove usa l'email con cui sei nel team Supabase (le altre non ricevono nulla) e conta
   2 email all'ora.
4. Prima di far provare l'app ad altri: SMTP personalizzato (serve un dominio), poi modello
   "Confirm signup" con `{{ .Token }}` e `EXPO_PUBLIC_EMAIL_OTP=1`.

Da fare in seduta 5: verifica dell'età (fornitore astratto + finto per i test, webhook firmato),
schermate tipo di profilo e stili, creazione del profilo.

### Seduta 5 — 2026-10-04

Fatto:
- **Verifica dell'età, lato server** (`services/api/app/age/`):
  - fornitore astratto (`AgeProvider`): il fornitore vero (D5) si aggiunge senza toccare il resto;
  - fornitore di prova con la sua "pagina del fornitore" (`/v1/dev/fake-age/…`, solo sviluppo,
    vietato in produzione dalla configurazione) che invia un webhook firmato come uno vero;
  - webhook firmati HMAC-SHA256 con timestamp (rifiutati se più vecchi di 5 minuti), confronto
    a tempo costante, rotazione del segreto, ripetizioni ignorate (vale il primo esito);
  - decisione pura e testata: con documento/SPID/CIE vale la data letta; con la stima da selfie
    si confronta con la data dichiarata e vince la fascia più protettiva; se non tornano si chiede
    un documento. "Sotto i 16" blocca per un anno solo se viene da un documento;
  - endpoint `GET /v1/age-verification`, `POST /v1/age-verification/sessions`,
    `GET /v1/age-verification/sessions/{id}`, `POST /v1/webhooks/age/{fornitore}`;
  - indirizzi di ritorno ammessi solo `wearx://` (più `exp://` e l'anteprima web in sviluppo):
    niente redirect aperti; una sola verifica aperta per volta, scade dopo un'ora; 5 tentativi l'ora.
  - Migrazione 0004: motivo dell'esito negativo; la data dichiarata esiste solo finché la
    verifica è aperta (lo impone un vincolo del database). Nessuna foto, documento o data di
    nascita salvati.
  - `/v1/config` espone la versione dei termini.
- **Onboarding nell'app** (passi 2-4 del prototipo): scelta del metodo (SPID/CIE compaiono quando
  si accende il flag), apertura della pagina del fornitore, attesa dell'esito, tipo di profilo
  (Business disattivato finché il flag è spento e sempre per i 16-17enni), scelta degli stili (i
  16-17enni non vedono gli stili 18+), creazione del profilo ed entrata nell'app. Se l'app viene
  riaperta a metà: data di nascita da reinserire, nickname recuperato dalla registrazione; se nel
  frattempo il nickname è stato preso si sceglie un altro al volo.
- Prova completa sull'anteprima web, con server e database veri e fornitore di prova: dalla
  verifica fino al feed, sia maggiorenne sia 16-17 anni (qui è emerso anche il caso "nickname
  preso nel frattempo", gestito). Screenshot: `docs/screens/seduta-05-onboarding.png`.
- Corretto: l'etichetta degli stili ("Stagionale", "18+") finiva al centro del riquadro.

Verifiche: 131 test API (+42) e 101 test app (+15); ruff, mypy, tsc puliti; bundle Android
compilato.

Note:
- Per provare la verifica dal telefono con Expo Go, l'API deve essere raggiungibile dal telefono
  (`WEARX_PUBLIC_API_URL` e `EXPO_PUBLIC_API_URL` con l'IP del computer): arriva con il deploy.
- Il feed mostra ancora tutti gli stili nelle chip in alto: diventano i tuoi stili con le sedute 6-7.

Da fare in seduta 6: stili lato server (ricerca, pagina stile, entrare/uscire da uno stile,
regole d'età).

### Seduta 6 — 2026-10-04

Fatto (API, `services/api/app/routers/styles.py`):
- `GET /v1/styles?q=`: elenco e ricerca. Trova anche senza accenti e maiuscole ("gala" → Galà),
  con refusi ("jppo" → Jappo) e dalle parole della descrizione ("tokyo" → Jappo); prima i nomi
  che iniziano con il testo, poi i contenuti, poi le somiglianze. Caratteri speciali (`%`, `_`,
  apici) trattati come testo normale.
- `GET /v1/styles/{slug}`: pagina dello stile (membri, se ci sei dentro, fit dell'ultima
  settimana; la griglia dei fit arriva con il feed).
- `PUT` / `DELETE /v1/styles/{slug}/membership`: entrare e uscire, ripetibili senza effetti
  doppi. `GET /v1/me/styles`: i tuoi stili in ordine di adesione (per le chip del feed).
- Regole: i 16-17enni non vedono né aprono né raggiungono gli stili 18+ (per loro "non esistono",
  stessa risposta di uno stile inesistente); stili fuori stagione o spenti spariscono; se uno stile
  diventa 18+ sparisce dagli stili dei minorenni; non si esce dall'ultimo stile visibile (anche
  con due uscite in contemporanea: le modifiche di una persona passano una alla volta); massimo
  30 stili; 60 modifiche l'ora.
- Compiuti 18 anni si passa da soli alla fascia 18+ (alla prima richiesta; funzione
  `app.promote_adults()` pronta anche per un job notturno).
- Migrazione 0005: funzione `app.fold()` (minuscolo, senza accenti) e indice di ricerca su di essa.

Verifiche: 155 test API (+24); ruff, mypy, tsc puliti.

Nota per dopo: il prototipo, quando la ricerca non trova nulla, dice "Proponilo tu: se raggiunge
500 adesioni, nasce". Le proposte di stile non sono nel piano: da decidere se aggiungerle
(insieme all'admin, seduta 17).

Da fare in seduta 7: stili nell'app (Esplora con ricerca, pagina stile, Aderisci/Esci, chip del
feed con i tuoi stili).

### Seduta 7 — 2026-10-05

Fatto (app):
- **Esplora**: ricerca con pausa di battitura (trova anche senza accenti e con refusi, grazie
  al server), stile stagionale in evidenza ("STAGIONALE · FINO AL 1 NOV"), griglia di tutti gli
  stili con numero di membri ("15,1k membri") ed etichetta "Aderito", stato vuoto, scheletri di
  caricamento, errore con "Riprova".
- **Pagina dello stile** (`/style/[slug]`): intestazione nel colore dello stile, membri, pulsante
  Entra / Sei dentro, regola del match al 70% dal prototipo, fit della settimana (la griglia dei
  fit arriva con il feed). Stile fuori stagione o 18+ per un minorenne: "Stile non disponibile".
- **Entrare e uscire si vede subito** (aggiornamento ottimistico su pagina, Esplora e feed); se il
  server rifiuta (es. ultimo stile rimasto) tutto torna com'era e compare il motivo.
- **Feed**: le chip in alto sono ora i TUOI stili, in ordine di adesione, più "+ Stili" che porta
  a Esplora.
- `ErrorNotice` con pulsante "Riprova"; nuovo componente `SearchField`; `StyleTile` con etichetta
  di stato a destra e descrizione su due righe.
- Prova completa nell'anteprima web con server e database veri: ricerca, pagina, entrata, uscita,
  rifiuto dell'uscita dall'ultimo stile. Screenshot: `docs/screens/seduta-07-stili.png`.

Verifiche: 111 test app (+10), 155 test API; tsc pulito; bundle Android compilato.
Trovato e corretto: nei test, le cache di React Query lasciavano timer accesi e jest non si
chiudeva (in CI sarebbe rimasto appeso).

Da fare in seduta 8: pipeline delle foto (URL firmati per il caricamento, quarantena, worker che
toglie i dati EXIF/GPS, crea le versioni WebP e il blurhash).

### Seduta 8 — 2026-10-05

Fatto (API + worker):
- **Archivio delle foto compatibile S3** (`app/storage.py`): bucket privato; il telefono carica
  direttamente sull'archivio con un POST firmato che contiene i limiti (solo il tipo dichiarato,
  massimo 15 MB, scade in 15 minuti); le foto si leggono solo con URL firmati a scadenza (1 ora).
  Funziona con Cloudflare R2, S3, MinIO (docker compose) e moto_server in locale.
- **Quarantena**: ogni foto arriva in `quarantine/<id>` e non è visibile a nessuno finché il
  worker non l'ha controllata. L'originale viene **sempre cancellato** dopo l'elaborazione.
- **Worker Arq** (`uv run arq app.worker.WorkerSettings`) che per ogni foto:
  - legge solo l'intestazione e rifiuta le "bombe di decompressione" (oltre 40 megapixel) senza
    decodificarle; accetta solo JPEG/PNG/WebP riconosciuti dal contenuto;
  - applica la rotazione EXIF, converte i colori in sRGB, poi **ricodifica da zero**: posizione
    GPS, modello del telefono, data e ogni altro metadato non arrivano mai online;
  - rifiuta foto troppo piccole (lato < 320 px) o troppo strette/larghe (oltre 1:2 o 2:1);
  - crea le versioni WebP a 1080, 640 e 320 px (mai ingrandite), il blurhash per l'anteprima
    sfocata, l'impronta SHA-256 e un hash percettivo (per ritrovare copie nella moderazione);
  - passa la foto al controllo di moderazione (interfaccia pronta, si riempie nella seduta 16):
    una foto bloccata non esce mai dalla quarantena.
- Endpoint: `POST /v1/media/uploads`, `POST /v1/media/uploads/{id}/complete`,
  `GET /v1/media/uploads/{id}`, `DELETE /v1/media/uploads/{id}`; foto altrui invisibili;
  massimo 20 caricamenti in sospeso e 60 all'ora.
- Pulizia automatica (ogni 30 minuti): caricamenti mai completati dopo 24 ore, foto mai usate in
  un post dopo 7 giorni.
- Migrazione 0006 (`app.media_uploads`), `python -m app.storage_init` per creare il bucket in locale.
- BlurHash scritto in casa e verificato contro la libreria di riferimento (quella rischiava di
  rompersi con Pillow 14).

Prova reale in locale con archivio S3, Redis e worker: foto da 12 megapixel con GPS → pronta in
meno di un secondo di lavoro, tre versioni WebP senza alcun metadato.

Verifiche: 186 test API (+31: rifiuti, rotazione, GPS, bombe, upload HTTP vero sull'archivio,
URL senza firma rifiutati, moderazione che blocca, pulizia); ruff, mypy, tsc puliti;
nessuna vulnerabilità nota nelle dipendenze.

Note:
- Arq richiede redis-py 5.x: la libreria è scesa da 8.1 a 5.3 (nessun impatto, test verdi).
- Quale archivio in produzione (Cloudflare R2 o lo Storage di Supabase, entrambi S3) si decide
  con l'infrastruttura (seduta 23).

Da fare in seduta 9: post lato server (creazione con le foto pronte, capi con brand/prezzo/link,
modifica, eliminazione) e la suite di test di autorizzazione.

### Seduta 9 — 2026-10-05

Fatto (API, `app/routers/posts.py`):
- **Pubblicazione** `POST /v1/posts`: stile, didascalia (max 140 caratteri, 3 righe, ripulita),
  da 1 a 10 foto già elaborate (nell'ordine del carosello) e fino a 8 capi con brand, nome,
  prezzo (EUR/USD/GBP/CHF), link al negozio e punto sulla foto.
  - Le foto si "prenotano" con un solo comando al database: due pubblicazioni in parallelo non
    possono usare la stessa foto; se qualcosa va storto non resta nulla a metà.
  - `Idempotency-Key`: se la rete cade e l'app ripete la richiesta, il post resta uno solo.
  - Link ai negozi solo https verso siti pubblici (niente IP, localhost, credenziali
    nell'indirizzo, porte strane); lo stesso negozio è una sola riga. Restano "da controllare"
    fino alla seduta 21; un link bloccato non mostra più l'indirizzo.
- **Lettura** `GET /v1/posts/{id}`: foto con URL firmati, capi, stile. L'autore compare solo se
  è Business, se sei tu o se lo segui; altrimenti il post è anonimo. Prezzi nascosti agli altri
  se l'autore lo ha scelto.
- **Modifica** `PATCH`: didascalia e capi; **cambio di stile una volta sola** per post.
- **Eliminazione** `DELETE`: il post sparisce, foto e capi cancellati subito (anche dall'archivio).
- **Chiavi d'ordine del portfolio** (`app/ranking.py`): i post nuovi vanno in cima; pronte le
  chiavi "in mezzo" per il riordino della seduta 14, verificate con 300 inserimenti casuali.
- **Suite di autorizzazione (IDOR)**: per post eliminati, nascosti dalla moderazione, di autori
  sospesi, in stili 18+ (per un minorenne) o inesistenti, lettura/modifica/eliminazione
  rispondono sempre 404 identico, così non si scopre nemmeno che il post esiste; un post visibile
  ma non tuo risponde 403 su modifica/eliminazione; blocchi in entrambe le direzioni.
- Migrazione 0007. Testi liberi con un'unica regola (`clean_text`: niente caratteri invisibili o
  che invertono il testo).

Prova reale in locale: foto della seduta 8 → post in Galà con un capo Armani → foto leggibile
con l'URL firmato; richiesta ripetuta → stesso post.

Verifiche: 234 test API (+48); ruff, mypy, tsc puliti.

Da fare in seduta 10: "Nuovo fit" nell'app (galleria con più foto, ordine del carosello, capi,
didascalia, caricamento che riprende se la rete cade).

### Seduta 10 — 2026-10-05

Fatto (app, schermata "Nuovo fit" a tutto schermo dal "+" della barra):
- **1 · Dalla galleria**: fino a 10 foto con la selezione multipla del telefono (nessun permesso
  sulla galleria intera: si vedono solo le foto scelte). Ogni foto parte subito, due alla volta:
  viene ridotta (lato lungo max 2160 px) e ricodificata in JPEG sul telefono, caricata
  sull'archivio con la barra di avanzamento, poi il server la pulisce ("Togliamo GPS e dati").
  Ordine del carosello con i pulsanti ‹ › (accessibili anche con VoiceOver/TalkBack), "×" per
  togliere una foto (cancella anche il caricamento sul server).
- **Caricamento con ripresa**: se la rete cade si riprova da solo dopo 1, 2, 4, 8 secondi; se il
  permesso firmato scade se ne chiede un altro; dopo 4 tentativi compare "Riprova". Le foto
  rifiutate dal server mostrano il motivo in italiano (es. "Formato troppo stretto o troppo
  largo") e non si riprovano.
- **2 · Stile del fit**: i tuoi stili per primi, poi gli altri visibili per la tua età.
- **3 · I capi**: brand, capo, prezzo (accetta "89", "89,90", "1.250,50"), link al negozio con
  avviso immediato se non è https; fino a 8 capi.
- **4 · Didascalia** con contatore 140.
- "Pubblica" si accende solo quando tutto è pronto; sopra c'è sempre scritto cosa manca
  ("Carichiamo le foto: 1 di 3", "Scegli lo stile del fit"...). Pubblicazione con chiave
  anti-doppioni: se la rete cade al momento sbagliato il post resta uno solo.
- La bozza resta se chiudi e riapri la schermata; "×" chiede conferma prima di scartarla.
- Trovato con la prova a schermo e corretto: su una foto rifiutata l'avviso copriva la "×" e
  non si poteva più toglierla.

Prova completa sull'anteprima web con archivio S3, worker e database veri: 3 foto (una troppo
piccola, rifiutata e tolta), ordine invertito, capo Armani a 1.250,50 € con link corretto da
http a https, pubblicazione → post salvato con foto nell'ordine giusto, prezzo 125050 centesimi.
Screenshot: `docs/screens/seduta-10-nuovo-fit.png`.

Verifiche: 154 test app (+43: prezzi, link, regole di pubblicazione, bozza, ripresa del
caricamento con rete che cade/permesso scaduto/foto rifiutata/annullamento, schermata completa);
234 test API; tsc pulito; bundle Android compilato.

Limiti noti: la bozza vive in memoria (se il sistema chiude l'app a metà, si ricomincia); i punti
dei capi sulla foto si aggiungono con la seduta 13, insieme alla loro visualizzazione nel feed.

Da fare in seduta 11: voti (voto anonimo 1-100, conferma dello stile, statistiche aggiornate
nella stessa operazione, test di concorrenza).

### Seduta 11 — 2026-10-05

Fatto (API, `app/routers/votes.py` e `app/votes.py`):
- **Voto da 1 a 100** con `PUT /v1/posts/{id}/vote`; si può cambiare; non si votano i propri
  fit; i post che non vedi rispondono 404 (stessa regola dei post).
- **Anonimato**: nella tabella dei voti non c'è chi ha votato, solo un'impronta
  HMAC-SHA256 calcolata con un segreto del server: serve solo a impedire il doppio voto.
- **Statistiche nella stessa operazione del voto** (conteggio, somma, media pesata,
  istogramma a fasce di 10 punti), sotto il lock della riga del post: esatte anche con molti
  voti insieme. Se lo stesso utente manda dieci voti in contemporanea ne resta uno.
- **Media nascosta finché non voti**: chi non ha ancora votato non la vede (nessuno si fa
  influenzare); l'autore la vede sempre. Se l'autore nasconde il numero di voti, gli altri
  vedono solo la media.
- **Conferma dello stile**: la domanda "È davvero <stile>?" va ai primi 30 votanti; con almeno
  10 risposte, sotto il 70% di sì il post esce dalla pagina dello stile (resta nel portfolio e si
  può ancora votare). Cambiando stile (una volta) la verifica riparte da zero. Vale solo la
  prima risposta di ciascuno.
- **Peso**: i voti degli account creati da meno di 24 ore contano la metà (difesa minima; la
  seduta 22 aggiunge attestazione del dispositivo e anomalie).
- `GET /v1/posts/{id}` include ora il riepilogo del voto.

Trovato dai test e corretto: il peso 0,5 veniva arrotondato a 0 dal database (mancava il tipo
esplicito del parametro).

Prova di carico reale in locale: 200 voti nello stesso istante su un post, un solo processo API
→ tutti accettati in 2,35 s, conteggio e somma esatti, istogramma coerente.

Verifiche: 250 test API (+16, compresi 40 voti in parallelo e 10 voti in parallelo della stessa
persona); ruff, mypy, tsc puliti.

Nota per la scala (sedute 22-24): su un singolo post virale i voti passano uno alla volta per
il lock; se servirà si accumulano in Redis e si scrivono a lotti.

Da fare in seduta 12: feed lato server (punteggio dei post, Redis per stile, cursore di
sessione, quota di esplorazione, ripiego senza Redis).

### Seduta 12 — 2026-10-05

Fatto (API, `app/feed.py` e `GET /v1/feed`):
- **Punteggio R = qualità x freschezza**. Qualità: media dei voti "prudente" (bayesiana,
  parte da 60 e conta 5 voti immaginari), così un solo 100 non porta un post in cima mentre venti
  voti da 90 sì. Freschezza: 0,35 + 0,65 x e^(-ore/36), finestra di 14 giorni. La formula esiste
  sia in SQL sia in Python e i test verificano che diano lo stesso numero.
- **Quota di esplorazione**: un posto ogni 5 va a un fit nuovo (meno di 48 ore, meno di 10 voti),
  in ordine casuale ma ripetibile: ogni post appena pubblicato ha la sua occasione.
- **Redis per stile**: classifica (ZSET) e "nuovi" per ogni stile, ricostruiti dal worker ogni
  5 minuti (che aggiorna anche `post_stats.hot_score`); un post appena pubblicato entra subito
  tra i nuovi del suo stile.
- **Sessione e cursore**: aprendo il feed si fissa l'elenco già filtrato per chi guarda (30
  minuti); il cursore lo scorre senza doppioni né salti anche se intanto cambiano i voti. Il
  cursore è firmato e legato all'utente e allo stile: manomesso o di un altro → 400; sessione
  scaduta → 410 (l'app ricarica).
- **Filtri per chi guarda**: niente post propri, niente post già votati, niente autori bloccati
  in nessuna direzione, regole d'età; un post cancellato o bloccato dopo l'apertura non arriva
  nelle pagine successive.
- **Ripiego senza Redis**: se Redis non risponde il feed si calcola da PostgreSQL con lo stesso
  ordine (il test confronta le due strade pagina per pagina).
- `empty_reason` dice all'app perché il feed è vuoto ("no_styles" / "no_posts").
- Lettura dei post riscritta "in blocco" (`app/post_views.py`): una pagina di 10 post = 4 query,
  mai una query per post.

Prova reale in locale con 5.000 post su 11 stili: apertura del feed 312 ms la prima volta
(classifiche da costruire), poi 39 ms; pagine successive 6 ms.

Verifiche: 263 test API (+13); ruff, mypy, tsc puliti.

Da fare in seduta 13: feed nell'app (card, carosello delle foto, capi sulla foto, slider del
voto con aggiornamento immediato).

### Seduta 13 — 2026-10-05

Fatto (app, `src/app/(tabs)/index.tsx` e `src/features/feed/`):
- **Feed vero** al posto del segnaposto: chip "Tutti" + i tuoi stili (e "+ Stili"), la regola
  della casa ("Qui non si commenta. Si vota da 1 a 100, in forma anonima."), scorrimento
  infinito con il cursore della seduta 12, tira giù per aggiornare, nessun doppione tra pagine.
  Se la sessione del feed scade (app aperta a lungo) si riparte dall'inizio da soli.
- **Card del fit**: avatar con il colore dello stile e le iniziali (o "Fit anonimo"), stile e
  "% match" quando ci sono abbastanza conferme, didascalia, riquadro "IL FIT" con marchio, capo,
  prezzo, **totale del look** e pulsante che apre il negozio nel browser interno.
- **Carosello**: foto 4:5 con anteprima sfocata (blurhash) mentre carica, la variante giusta per
  lo schermo (320/640/1080), scorrimento a pagine, zone di tocco a destra/sinistra, contatore
  "2/3" e pallini.
- **Capi sulla foto**: il pulsante "Capi · n" mostra i punti con il marchio sopra la foto
  (solo i capi di quella foto); "Nascondi" li toglie.
- **Slider del voto 1-100** fatto su misura: si trascina o si tocca il binario, − e + per un
  punto, numero grande e la "frase" del voto (es. "Fit pazzesco"); con VoiceOver/TalkBack si
  regola con i gesti su/giù. Il trascinamento non fa scorrere il feed.
- **Voto immediato**: appena premi "Vota" la card passa a "MEDIA COMMUNITY · il tuo 92" senza
  aspettare; la media arriva con la risposta del server. Se il server rifiuta (post sparito,
  troppi voti) si torna com'era con un messaggio chiaro.
- **"È davvero Galà?"** Sì/No compare solo quando il server lo chiede (primi 30 votanti).
- I tuoi fit mostrano "IL TUO FIT · MEDIA" invece dello slider.

Provato davvero sul web con API, worker, Redis e archivio foto locali: 4 fit pubblicati con la
pipeline vera, trascinamento dello slider fino a 92, conferma dello stile, voto registrato nel
database, media mostrata, carosello a 3 foto navigato.

Verifiche: 168 test app (+14: testi e calcoli, slider, card, capi sulla foto, voto ottimistico
con conferma, rifiuto con ripristino, pagine successive, filtro per stile, stati vuoti, errore
di rete); tsc pulito; export Android ok.

Schermate: `docs/screens/seduta-13-feed.png`.

Da fare in seduta 14: portfolio (griglia dei tuoi fit, riordino trascinando, copertina, capsule).

### Seduta 14 — 2026-10-05

Fatto (API, `app/portfolio.py` e `app/routers/portfolio.py`, migrazione 0008):
- **`GET /v1/users/{nickname}`**: profilo con bio, tipo di account, stili, capsule e statistiche
  (fit, voto medio, voti ricevuti). **`GET /v1/users/{nickname}/posts`**: griglia a pagine con
  cursore, filtrabile per capsula; ogni fit ha la prima foto, lo stile, la didascalia e il voto.
- **Chi vede cosa**: il proprio portfolio sempre (anche i fit "fuori stile" o nascosti, con
  l'etichetta); un account Business o un privato che segui (richiesta accettata) sì; un privato
  non seguito mostra solo nickname, bio e numero di fit, la griglia risponde "account privato"
  (i follow arrivano con la seduta 15). Con un blocco la persona "non esiste". Le medie seguono la
  regola dei voti: un fit altrui mostra la media solo se l'hai votato; la media complessiva di
  un'altra persona compare solo con almeno 3 fit votati (con un fit solo svelerebbe quel voto).
- **Ordine e copertina** (`PUT /v1/me/portfolio/order`, indice frazionario): spostare un fit
  cambia una sola riga. Il primo è la copertina; dal primo riordino resta quella scelta e **i fit
  nuovi entrano subito sotto la copertina** invece di rubarle il posto; se elimini la copertina,
  la copertina diventa il fit che ora è primo. Riordini in parallelo della stessa persona passano
  uno alla volta. Spostando sempre nello stesso punto le chiavi si allungano: oltre 40 caratteri
  si riscrivono tutte corte (verificato con 250 spostamenti), e chiavi uguali di dati vecchi si
  sistemano da sole.
- **Capsule** (`/v1/me/capsules`): crea, rinomina, elimina (i fit restano nel portfolio), massimo
  12 anche con richieste in parallelo, nomi senza doppioni ignorando le maiuscole ("Estate" =
  "estate"), massimo 30 caratteri. Un fit va in una capsula con `PATCH /v1/posts/{id}`; capsule
  altrui → rifiutate. Gli altri vedono solo le capsule con dentro fit che possono vedere.

Fatto (app):
- **Profilo-portfolio** come nel prototipo: anello col colore d'accento e iniziali, statistiche,
  @nickname con PRIVATO/BUSINESS, bio, stili (i primi 6 + "+N"), schede delle capsule, griglia a
  due colonne con posizione "01", badge COPERTINA, stile, titolo, voto grande e numero di voti.
- **Modifica ordine**: frecce ‹ › su ogni fit (anche con VoiceOver/TalkBack, che annuncia la nuova
  posizione); lo spostamento si vede subito e torna com'era se il server dice no.
- **Capsule**: pannello per crearle, rinominarle ed eliminarle (con conferma).
- **Dettaglio del fit** (`/post/[id]`, tocco su un fit): card completa e, se è tuo, "Capsula"
  (con "crea e aggiungi"), "Metti in copertina", "Elimina fit" con conferma.
- Il pannello impostazioni (icona in alto) per ora contiene "Esci"; privacy e sicurezza arrivano
  con la seduta 20. Pubblicando un fit il portfolio si aggiorna.

Provato davvero sul web con API, worker e archivio foto locali: 6 fit pubblicati con la pipeline
vera, riordino con le frecce, ordine ritrovato identico dopo aver ricaricato la pagina, scheda
"Serate", pannello capsule, dettaglio con la capsula.

Verifiche: 283 test API (+20: ordine contro un modello con 60 spostamenti casuali, copertina e
fit nuovi, ribilanciamento, riordini in parallelo, cursore, privacy, blocchi, medie nascoste,
fit nascosti e stili 18+, capsule e loro limiti anche in parallelo); 187 test app (+19); ruff,
mypy, tsc puliti; export Android ok.

Schermate: `docs/screens/seduta-14-portfolio.png`.

Da fare in seduta 15: account privati (richiesta di follow, accetta/rifiuta, blocchi, pagina del
profilo di un'altra persona dal feed, regole 16-17 / 18+).

### Seduta 15 — 2026-10-05

Fatto (API, `app/people.py`, `app/routers/social.py`, migrazione 0009):
- **Follow con richiesta**: `POST/DELETE /v1/users/{nickname}/follow`. Un account privato riceve
  una richiesta da accettare; un Business si segue subito; passando a Business le richieste in
  attesa diventano follow. Ripetibile (anche 8 richieste in contemporanea = una sola riga);
  100 al giorno.
- **Richieste ed elenchi**: `GET /v1/me/follow-requests` + `POST` per accettare o rifiutare,
  `GET /v1/me/followers`, `/v1/me/following`, `/v1/me/blocks` (a pagine, dal più recente),
  `DELETE /v1/me/followers/{nickname}` per togliere un follower.
- **Blocchi**: `PUT/DELETE /v1/users/{nickname}/block`. Bloccare toglie i follow e le richieste
  nei due sensi; da quel momento l'uno per l'altro non esistono (profilo, griglia, fit, feed). Si
  può bloccare chiunque si conosca per nickname. Sbloccando ci si rivede, ma i follow vanno
  richiesti di nuovo.
- **Profilo**: contatori follower/seguiti, rapporto con chi guarda (segui, richiesta inviata, ti
  segue), richieste in attesa sul proprio profilo.
- **Tutele 16-17 (sez. 14.1)**, in un solo punto per tutta l'app:
  - un maggiorenne non trova il profilo di un 16-17enne (risposta identica a "non esiste"),
    quindi non può chiedergli il follow; un 16-17enne vede gli adulti e può chiedere di seguirli;
  - i fit pubblicati da un 16-17enne li vedono solo altri 16-17 (feed, pagina, voto, griglia);
  - scelta presa: **i fit pubblicati quando aveva 16-17 anni restano tra 16-17 anche dopo i 18**
    (colonna `posts.minor_author`); quelli nuovi sono visibili a tutti;
  - una richiesta vecchia di chi nel frattempo ha compiuto 18 anni non si può accettare.

Fatto (app):
- **Profilo di un'altra persona** (`/user/[nickname]`): si apre toccando il nome dell'autore nel
  feed. Pulsante Segui → "Richiesta inviata" (tocca di nuovo per ritirarla) → "Segui già"
  (smettere chiede conferma se l'account è privato). "Account privato" finché non si è accettati.
  Menu "…" con Blocca e conferma.
- **Il tuo profilo**: contatori follower · seguiti, banner "Richieste di follow" con il numero,
  icona "Trova persone".
- **Persone** (`/people`): Richieste (Accetta / ×), Follower (Rimuovi), Seguiti (Non seguire
  più), Bloccati (Sblocca). Tutto si vede subito e torna com'era se il server dice no.
- **Trova persone** (`/find`): nickname esatto → scheda con Segui. Non è una ricerca: nessun
  elenco di persone da sfogliare (la specifica la esclude per la v1).
- Nel pannello Account: "Account bloccati".

Provato davvero sul web: due richieste in arrivo, una accettata (compare tra i follower);
nickname cercato, richiesta inviata, profilo bloccato finché l'altra persona non accetta, poi la
griglia si apre; menu Blocca.

Verifiche: 295 test API (+12); 200 test app (+13); ruff, mypy, tsc puliti; export Android ok.

Schermate: `docs/screens/seduta-15-account-privati.png`.

Da fare in seduta 16: moderazione lato server (segnalazioni con priorità, azioni dei moderatori,
classificatore immagini e hash dietro interfacce, pulsante "Segnala").

### Seduta 16 — 2026-10-05

Fatto (API, `app/moderation/`, migrazione 0010):
- **Controlli sulle foto prima della pubblicazione**, dietro due interfacce:
  - *liste di impronte*: sempre attiva la lista locale (foto rimosse dai moderatori, anche
    ricompresse o leggermente modificate, e impronte indicate dalle autorità); il servizio
    esterno per il materiale illegale noto si collega quando l'accesso è concesso;
  - *classificatore* (nudità, sesso, violenza, armi, odio): interfaccia pronta, si collega con il
    fornitore scelto. Sopra una soglia la foto non passa; tra due soglie passa ma il fit entra in
    coda; **per i 16-17 soglie più severe e il fit resta nascosto finché un moderatore non decide**.
  - Corrispondenza con materiale illegale noto: foto rifiutata e mai salvata, account sospeso
    subito, caso P0 aperto per i moderatori.
- **Parole vietate** (insulti, odio, istigazione all'autolesionismo, IT/EN) in nickname, bio,
  didascalie, brand, capi e nomi delle capsule; riconosce anche "pu77ana", "p.u.t.t.a.n.a",
  lettere ripetute, due parole attaccate. Chi segnala o fa reclamo può citare l'insulto.
- **Segnalazioni** (`POST /v1/reports`) su fit, profili e link, 20 al giorno, una aperta per
  persona e contenuto:
  - P0 *un minore è in pericolo*: il fit si nasconde subito; l'account si sospende se lo
    segnalano almeno 2 persone diverse (con una sola chiunque potrebbe far sospendere chiunque);
  - P1 *nudità, molestie*: il fit si nasconde dopo 3 persone diverse con account di almeno 24 ore;
  - P2 *spam, stile sbagliato, link, foto rubata, altro*: nessuna azione automatica.
- **Decisioni con motivazione** (art. 17 DSA): ogni azione ha il testo che la persona legge (cosa,
  perché, automatica o umana, come fare reclamo). **Scala delle sanzioni**: avviso →
  pubblicazione sospesa 7 giorni → account chiuso; P0 confermato → chiusura subito.
- **Reclami** (art. 20 DSA): uno per decisione, entro 6 mesi, anche da account sospeso; lo decide
  un moderatore **diverso** da chi ha deciso; se accolto annulla tutto (fit di nuovo visibile,
  sanzione decisa insieme tolta, foto di nuovo ripubblicabili).
- **Strumenti dello staff** (`/v1/admin/...`, interfaccia web con la seduta 17): coda raggruppata
  per contenuto e ordinata per priorità e scadenza (P0 1 ora, P1 24 ore, P2 72 ore, "in ritardo"),
  anteprima con la foto più piccola, decisioni (archivia, nascondi, rimuovi, ripristina) con
  sanzione automatica o scelta, scheda della persona con lo storico, reclami. Solo chi è nella
  tabella dello staff **e** ha fatto l'accesso con il secondo fattore; ogni azione nel registro
  di audit (non modificabile). Archiviare una segnalazione annulla le misure automatiche.

Fatto (app):
- **Segnala** ("…" su ogni fit altrui e nel menu del profilo): motivo, dettagli facoltativi,
  conferma con i tempi di revisione; per "un minore è in pericolo" anche "chiama il 112".
- **Avvisi della moderazione** (Account › Avvisi): ogni decisione con motivo e testo completo,
  "Fai reclamo", esito del reclamo con la nota del moderatore.
- Sul proprio fit nascosto: riquadro "Nascosto dalla moderazione" con il link al motivo.
- **Account sospeso**: la schermata mostra la decisione e permette il reclamo senza entrare
  nell'app. Pubblicazione sospesa: "Nuovo fit" dice fino a quando.

Provato davvero sul web: segnalazione di un fit dal feed, coda dello staff, un moderatore nasconde
un fit con avviso automatico, l'autore vede il riquadro, il motivo e fa reclamo.

Verifiche: 311 test API (+16); 209 test app (+9); ruff, mypy, tsc puliti; export Android ok.

Note e decisioni da confermare:
- Una sola segnalazione P0 nasconde il fit ma non sospende l'account (la specifica diceva
  sospensione automatica): serve a evitare che chiunque possa far chiudere chiunque.
- Le foto con corrispondenza di materiale illegale non vengono conservate: restano impronte e
  caso aperto. Cosa conservare e come lo decide la procedura con il legale.
- Il modulo web per segnalare senza l'app (art. 16 DSA) arriva con il sito.

Schermate: `docs/screens/seduta-16-moderazione.png`.

Da fare in seduta 17: pannello web dello staff (Next.js): coda di moderazione con foto sfocate,
decisioni rapide, reclami, persone, stili, registro di audit.

### Seduta 17 — 2026-10-05

Fatto (`apps/admin`, Next.js 16, solo per lo staff):
- **Accesso**: email e password Supabase, poi **sempre** il codice dell'app di autenticazione
  (al primo accesso si configura con il QR). Sessione solo nella scheda: chiusa la scheda si
  rientra da capo. Chi non è nello staff non vede nulla. In locale si entra incollando un token
  di prova (spento fuori dallo sviluppo). Nessuna chiave segreta nel pannello: se ce ne fosse
  una, il pannello si rifiuta di partire.
- **Panoramica**: P0/P1 aperti, in ritardo, reclami aperti, fit e voti di oggi, persone (nuove in
  7 giorni), account sospesi; contatori anche nel menu.
- **Coda**: segnalazioni raggruppate per contenuto, filtro per priorità, scadenza visibile.
  Le foto sono **sfocate** finché non si preme "Mostra" (per i P0 con l'avviso "guarda solo se
  serve"). Motivo, sanzione (per i P0 proposta la scala automatica), nota interna. **Scorciatoie
  da tastiera**: J/K scorri, V mostra, A archivia, N nascondi, R rimuovi (chiede conferma).
- **Reclami**: decisione contestata, testo del reclamo, risposta obbligatoria per la persona,
  accogli o respingi (l'API impedisce che decida chi aveva deciso la prima volta).
- **Persone**: ricerca per nickname; scheda con sanzioni degli ultimi 12 mesi, prossima tappa
  della scala, interventi (avviso, sospensione pubblicazione, chiusura), "togli le limitazioni",
  storico con le decisioni annullate barrate.
- **Solo admin**: **Stili** (crea e modifica: nome, indirizzo, descrizione, colore, età minima,
  stagione dal/al, ordine, visibile o no), **Staff** (aggiungi, cambia ruolo, togli; mai senza
  almeno un admin), **Registro di audit** a pagine (aprire un fit o una scheda viene registrato).
- Stile del pannello come l'app (stessi colori e caratteri), protezioni del browser strette
  (nessun contenuto esterno, niente iframe, non indicizzato).

Fatto (API): `/v1/admin/me`, numeri, fit in qualsiasi stato con foto, capi e segnalazioni,
ricerca persone, riattivazione, stili, staff, audit (migrazione 0011).

Corretto provando davvero il pannello:
- Annullare un fit (reclamo accolto o "Rendi visibile" dalla coda) toglie anche l'avviso deciso
  insieme, ma l'avviso **continuava a contare** nella scala delle sanzioni: ora ogni decisione
  annullata è segnata (`reversed_at`) e non conta più; un secondo annullamento non fa nulla.
- Il messaggio per l'annullamento dell'avviso collegato ora è suo ("Annullata anche la sanzione
  decisa insieme al fit") e non ripete "il tuo reclamo è stato accolto"; archiviare una
  sospensione automatica dice "un moderatore ha verificato".
- Tre moduli mandavano all'API campi in più e venivano rifiutati (reclami, modifica stile,
  ruolo staff): ora mandano solo ciò che serve, con test.

Provato davvero (browser, 1440×900): accesso admin, panoramica, coda P0 con foto sfocata, P1
nascosto da tastiera, reclamo accolto da un altro moderatore, scheda della persona con avviso
annullato e scala tornata ad "avviso", nuovo stile stagionale "Après Ski", registro.

Verifiche: 319 test API (+8); 10 test pannello; 209 test app; ruff, mypy, tsc puliti; build del
pannello ok; nuovo job CI "Pannello staff".

CI di nuovo verde (era rossa dalla seduta 15): un test dell'app superava a volte i 5 secondi sui
computer di GitHub (ora 20) e il controllo dei segreti scambiava per segreta la chiave
publishable di Supabase, che è pubblica (eccezione solo per quella; le chiavi segrete restano
bloccate). I test falliti ora compaiono come annotazioni nella pagina della CI.

Decisione: le **proposte di stile** dagli utenti ("Proponilo tu… 500 adesioni") slittano dopo
la v1; per ora gli stili li crea un admin dal pannello.

Schermate: `docs/screens/seduta-17-admin.png`.

Da fare in seduta 18: notifiche ed eventi: push con Expo (voti ricevuti, nuovi follower e
richieste, avvisi della moderazione, esito dei reclami), lista delle notifiche nell'app,
raccolta degli eventi d'uso con lista consentita.

### Seduta 18 — 2026-10-05

Fatto (API, migrazione 0012):
- **Registro delle notifiche**: ogni notifica nasce nella stessa operazione che la causa (se
  l'azione fallisce, la notifica non esiste). Tipi: richiesta di follow, nuovo follower,
  richiesta accettata, traguardo di voti, decisione della moderazione, esito del reclamo.
  - Richiesta accettata: la riga diventa "ha iniziato a seguirti" senza un secondo push;
    richiesta ritirata o rifiutata: sparisce. Bloccare cancella le notifiche tra le due persone
    e una persona bloccata non ne genera.
  - Segui, smetti, segui di nuovo: una sola riga e al massimo un push ogni 24 ore.
  - **Voti**: mai un push per ogni voto (dall'orario si potrebbe capire chi ha votato), solo i
    traguardi 10, 25, 50, 100, 250, 500, 1000… controllati ogni 10 minuti; i fit già
    pubblicati partono dal prossimo traguardo (niente valanga di notifiche al primo avvio).
  - Moderazione: una notifica per decisione; gli annullamenti dovuti a un reclamo li racconta
    l'esito del reclamo ("Reclamo accolto"), senza doppioni.
- **Push con Expo**: un lavoro ogni minuto spedisce le notifiche in attesa; più notizie insieme
  diventano un solo push ("Hai 4 nuove notifiche"); il numero sull'icona dell'app = non lette.
  Sul telefono (schermo bloccato) la moderazione dice solo "Hai un nuovo avviso della
  moderazione". Telefoni non più esistenti tolti grazie alle ricevute di Expo. Se Expo non
  risponde si riprova ogni 5 minuti per 24 ore. **16-17 anni: niente push tra le 22 e le 7**
  (arrivano alle 7). Un telefono riceve i push di un solo account; all'uscita smette.
- Endpoint: `GET /v1/notifications` (a pagine), `/unread`, `POST /read`,
  `PUT/DELETE /v1/me/push-tokens`, `GET/PATCH /v1/me/notification-settings`.
- **Eventi d'uso** (`POST /v1/events`), lista consentita di 4 soli eventi, quelli che servono
  agli Insight della seduta 19: fit visto, fit aperto, tocco sul link di un negozio, profilo
  visitato. Nessun campo libero, nessun identificativo del telefono, nessun IP; chi l'ha fatto
  è uno pseudonimo; i propri fit e il proprio profilo non contano. Eventi grezzi in partizioni
  mensili, cancellati dopo circa 3 mesi (lavoro notturno).

Fatto (app):
- **Campanella** nel feed con il numero delle non lette; **schermata Notifiche** con le nuove
  evidenziate, Accetta/Rifiuta direttamente sulle richieste, miniatura del fit, tocco che porta
  al profilo, al fit o agli avvisi.
- **Attiva le notifiche**: il permesso del telefono si chiede solo quando la persona tocca
  "Attiva" (mai all'avvio); se l'ha negato, spiega come riattivarlo.
- **Impostazioni › Notifiche** (anche dal menu Account): follow, voti, moderazione.
- Tocco su un push: apre solo schermate interne note (un push non può aprire un sito).
- Eventi raccolti nel feed (fit visto almeno 1 secondo per il 60%), sul fit aperto, sui link
  dei negozi e sui profili; partono a gruppi ogni 30 secondi o quando l'app va in background.

Provato davvero (web, 390×844, worker acceso): campanella con 4, lista con richieste, traguardo
"1000 voti", reclamo accolto; Accetta da lista; impostazioni; tocco sul traguardo apre il fit;
il worker ha spedito un solo push "Hai 4 nuove notifiche" con numero 4 sull'icona; eventi
"fit visto" arrivati al database.

Corretto grazie a test e prova reale:
- la coda degli eventi restava "in invio" per sempre dopo un giro vuoto e non spediva più nulla;
- sul web i pulsanti Accetta/Rifiuta erano dentro la riga toccabile (pulsante dentro pulsante);
- senza il punto di partenza dei traguardi, al primo avvio ogni fit già pubblicato avrebbe
  mandato la sua notifica di voti.

Verifiche: 336 test API (+17); 224 test app (+15); ruff, mypy, tsc puliti.

Note e decisioni da confermare:
- I push veri partono solo con il progetto EAS e le chiavi Apple/Google (seduta 23 e 25):
  fino ad allora tutto funziona dentro l'app e il server scrive i push nel registro.
- Eventi solo per gli Insight, nessuna statistica d'uso generica: se servisse (es. quante
  persone aprono l'app) andrebbe aggiunta con consenso esplicito.
- Una persona può gonfiare le visualizzazioni di un fit al massimo di 1 al giorno (gli Insight
  contano persone diverse): i controlli anti-abuso più forti arrivano con la seduta 22.

Schermate: `docs/screens/seduta-18-notifiche.png`.

Da fare in seduta 19: Insight per chi pubblica (riepilogo notturno degli eventi, API, schermata
Insight con soglie minime per non far riconoscere chi ha guardato o votato).

### Seduta 19 — 2026-10-05

Fatto (API, migrazione 0013):
- **Riepilogo notturno** (3:40, ora italiana): per ogni fit e giorno, persone diverse che l'hanno
  visto, aperto, che hanno toccato un link di un negozio; voti ricevuti e loro somma; per ogni
  autore, persone diverse che hanno visitato il profilo. Ricalcola ieri e l'altro ieri (gli eventi
  arrivano fino a 24 ore dopo); al primo avvio ricostruisce gli ultimi 90 giorni. Ripetibile
  senza doppioni. Gli orari dei lavori del worker ora sono in ora italiana.
- `GET /v1/me/insights?days=7|28|90`: totali del periodo con la variazione rispetto al periodo
  prima, media dei voti, andamento giorno per giorno (per settimana sui 90 giorni), i 5 fit più
  visti. Solo i propri dati. Account o fit cancellati: spariscono anche i loro totali.
- **Soglie di riservatezza**: i numeri da 1 a 4 non si mostrano («<5»), lo zero sì; la media dei
  voti solo da 5 voti in su e mai giorno per giorno; la variazione percentuale solo se entrambi i
  periodi superano la soglia.
- Flag `insights` acceso.

Fatto (app):
- Pulsante **Insight** (icona grafico) in alto nel proprio profilo.
- Schermata Insight: periodo 7/28/90 giorni, sei numeri (visualizzazioni, voti, media, aperture,
  click ai negozi, visite al profilo) con ▲/▼ e percentuale rispetto al periodo prima, grafico a
  colonne (viste o voti) dove si tocca un giorno per leggere il valore, i giorni con «meno di 5»
  disegnati come contorno vuoto (forma diversa, non solo colore), i fit più visti con miniatura,
  nota che spiega le soglie.

Provato davvero (web, 390×844) con due mesi di attività simulata (20.672 eventi, 2.417 voti):
7, 28 e 90 giorni, tocco su un giorno di calo, passaggio ai voti, fit più visti.

Corretto provando: il periodo nell'indirizzo veniva rifiutato (7/28/90 come testo), la prima
settimana dei 90 giorni partiva prima del periodo, titolo del grafico e valore massimo
impaginati meglio; il profilo di un'altra persona non chiede più la configurazione.

Verifiche: 341 test API (+5); 227 test app (+3); ruff, mypy, tsc puliti.

Note e decisioni da confermare:
- Insight aggiornati una volta per notte (dati fino a ieri): aggiornarli ogni ora renderebbe
  più facile capire chi ha guardato o votato in un certo momento.
- Da valutare in seduta 22 (hardening): sul proprio fit la media e il numero dei voti si
  aggiornano a ogni voto. Chi pubblica, se sa che un amico sta votando proprio in quel momento,
  può ricavare il suo voto dal cambio della media. Proposta: aggiornare media e conteggio a
  intervalli (es. ogni ora) invece che in tempo reale.
- Visualizzazioni = persone diverse per giorno, sommate sul periodo: chi guarda lo stesso fit in
  due giorni diversi conta due volte (il numero esatto di persone uniche sul periodo
  richiederebbe di tenere più a lungo gli eventi grezzi).

Schermate: `docs/screens/seduta-19-insight.png`.

Da fare in seduta 20: privacy e sicurezza nell'app (dispositivi collegati, scarica i tuoi dati,
cancellazione dell'account con 30 giorni per ripensarci, impostazioni) e recupero password.

### Seduta 20 — 2026-10-05

Fatto (API, migrazione 0014):
- **Dispositivi collegati**: l'app dice "sono qui" all'avvio e al ritorno in primo piano (nome del
  telefono, sistema, versione). Elenco con "questo dispositivo"; **Esci** da un dispositivo o da
  **tutti gli altri**: da quel momento l'API rifiuta i token di quell'accesso (anche rinnovati) e
  quel telefono smette di ricevere push; l'app lì esce da sola.
- **Scarica i tuoi dati** (GDPR art. 15 e 20): archivio ZIP preparato in background con LEGGIMI,
  profilo, consensi, esito della verifica dell'età, stili, fit con capi/prezzi/link e foto,
  capsule, follow e blocchi, **voti dati** (ritrovati ricalcolando lo pseudonimo, solo per te),
  segnalazioni, moderazione e reclami, notifiche, dispositivi, eventi degli Insight. Notifica
  quando è pronto; scaricabile 7 giorni (link valido un'ora); uno al giorno.
- **Cancellazione dell'account con 30 giorni**: conferma scrivendo il proprio nickname; da subito
  profilo, fit e capsule invisibili a tutti, fuori dagli altri dispositivi, niente push; entro 30
  giorni si annulla rientrando. Poi un lavoro notturno cancella foto, archivi, dati e l'utente di
  Supabase Auth. Restano senza alcun collegamento con la persona: voti dati (dentro le medie) e
  decisioni di moderazione (rapporti di trasparenza DSA).
- Un account in cancellazione può solo vedere il suo stato e annullare (403 altrove).

Fatto (app):
- **Privacy e sicurezza** (Account): nascondi i prezzi, nascondi il numero dei voti, cambia
  password, dispositivi collegati, notifiche, scarica i tuoi dati, cancella l'account, esci.
- **Password dimenticata?** nell'accesso: email, poi codice a 6 cifre (con l'SMTP) o link nella
  mail; nuova password con le stesse regole della registrazione (robustezza, controllo delle
  password violate); la risposta è identica che l'email esista o no; dopo il cambio si esce da
  tutti gli altri dispositivi. Finché la nuova password non è salvata l'app resta sulle schermate
  di accesso.
- **Cambia password** da dentro l'app: serve quella attuale.
- Schermata **Account in cancellazione** con la data e "Annulla la cancellazione".

Provato davvero (web, 390×844, worker acceso): impostazioni, dispositivi (uscita da un iPhone),
archivio chiesto, preparato dal worker, notificato e scaricabile, cancellazione con nickname,
schermata di cancellazione, annullamento e ritorno al feed.

Verifiche: 346 test API (+5); 239 test app (+12); ruff, mypy, tsc puliti.

Note e decisioni da confermare:
- Durante una **sospensione** l'account non si può cancellare (i dati possono servire alle
  verifiche e alle autorità): la persona scrive al supporto.
- I **voti dati** da chi cancella l'account restano nelle medie, anonimi: toglierli cambierebbe
  le medie dei fit di altri.
- La prova reale di "password dimenticata" con le mail vere si fa quando c'è l'SMTP (prima della
  beta); oggi è coperta dai test.

Schermate: `docs/screens/seduta-20-privacy.png`.

Da fare in seduta 21: account Business e link ai negozi (controllo dei link, redirect, click).

### Seduta 21 — 2026-10-05

Fatto (API, migrazione 0015):
- **Controllo dei link ai negozi** (worker, ogni 2 minuti): per ogni link, domini bloccati dallo
  staff (anche i sottodomini), Google Safe Browsing (se c'è la chiave) e visita sicura: solo
  https, solo indirizzi pubblici (mai la rete interna), al massimo 5 redirect controllati uno per
  uno. Esiti: **sicuro**; **non più disponibile** (pagina 404/410 o sito inesistente, oppure 3
  errori di fila); **bloccato** (sito pericoloso o dominio bloccato). Ricontrolli: sicuri ogni 7
  giorni, non disponibili ogni giorno.
- **Redirect con conteggio dei clic**: i capi nell'app aprono `/r/<codice firmato>`; si contano i
  clic sul link e sul fit (senza salvare chi ha cliccato), poi si va al negozio. Un link bloccato
  mostra una pagina "Abbiamo fermato questo link" e non prosegue. Codici falsificati o di capi
  modificati: "link non più disponibile".
- **Account Business**: fino a 5 siti del negozio, **verificati** pubblicando un file con un codice
  su `https://<sito>/.well-known/wearx-verify.txt`; un sito verificato appartiene a un solo
  account. I capi che puntano a un sito verificato dell'autore mostrano il **segno di negozio
  verificato** e il clic arriva al negozio con `utm_source=wearx` (il negozio vede quante visite
  porta WearX). Tornando a privato i siti verificati si tolgono.
- Pannello staff: pagina **Domini bloccati** (blocca/sblocca, con quanti link colpisce; tutto nel
  log di audit). Bloccare ferma subito tutti i link verso quel sito; sbloccare li ricontrolla.

Fatto (app):
- Capi: segno di negozio verificato, "Link non più disponibile" e "Link rimosso per sicurezza"
  (senza freccia né link apribile).
- Impostazioni → Account (solo maggiorenni): **Tipo di account** (Privato/Business con conferma)
  e **I tuoi negozi** (aggiungi, istruzioni per la verifica, Verifica, motivo se non riesce,
  rimuovi). I siti verificati compaiono sul profilo.

Provato davvero (web, 390×844 e pannello staff): fit di un Business con capo verificato, link non
disponibile e link bloccato; clic → redirect → contatore a 1; pagina del link bloccato; verifica
di un sito non raggiungibile con il motivo spiegato; blocco e sblocco di un dominio dal pannello.

Verifiche: 350 test API (+4); 244 test app (+5); 11 test del pannello (+1); ruff, mypy, tsc
puliti; build del pannello ok.

Note e decisioni da confermare:
- Risposte 401/403/429 dei negozi contano come "sito raggiungibile": molti e-commerce respingono i
  robot, e segnarli come rotti toglierebbe link buoni.
- `utm_source` si aggiunge **solo** ai siti verificati dei Business (gli altri link restano come
  li ha scritti l'autore).
- Verifica dei siti solo con il file (niente record DNS per ora). Shopify e piattaforme simili di
  solito non permettono file in quel percorso: per loro servirà la verifica con record DNS (da
  aggiungere se i primi negozi lo chiedono).
- I clic per singolo capo negli Insight non ci sono ancora (oggi: totale per fit).
- Rischio residuo documentato: "DNS rebinding" tra il controllo dell'indirizzo e la connessione;
  si chiude isolando la rete del worker (seduta 23).

Schermate: `docs/screens/seduta-21-business.png`, `docs/screens/seduta-21-admin-domini.png`.

Da fare in seduta 22: hardening (attestazione del dispositivo, anti-abuso dei voti, media e numero
dei voti sul proprio fit aggiornati ogni ora, Semgrep, scansione ZAP).

### Seduta 22 — 2026-10-05

Fatto (API, migrazione 0016):
- **Media e numero dei voti aggiornati ogni ora** (deciso in seduta 19), per tutti: autore e
  chi ha votato vedono valori pubblicati da un lavoro orario, non quelli in tempo reale. In più:
  la media compare **da 5 voti** e si aggiorna solo quando sono arrivati **almeno 3 voti nuovi o
  cambiati** dall'ultima volta. Così dal cambio della media non si ricava il voto di una
  persona, nemmeno con un secondo account. Il numero dei voti si aggiorna ogni ora. Feed e
  staff usano i valori in tempo reale; traguardi di voti, profilo, griglia del portfolio ed
  export dei dati usano quelli pubblicati.
- **Voti sospetti** (controllo orario, prima della pubblicazione): stesso voto (±1) su almeno 30
  fit in 7 giorni (comportamento da script) e almeno 8 voti in 24 ore ai fit dello stesso
  autore tutti ≥95 o tutti ≤10 (spinta o affossamento mirato). I voti trovati non contano più
  (né nella media né nel numero), per 30 giorni anche quelli nuovi; chi ha votato non se ne
  accorge. Ricalcolo esatto delle statistiche dai voti. **Raffica**: più di 40 voti in un minuto
  → 429.
- **Verifica del dispositivo**: App Attest su iPhone (chiave nel Secure Enclave, attestata una
  volta, poi firma a ogni nuovo accesso; catena di certificati fino alla radice Apple, contatore
  anti-riuso) e Play Integrity su Android (verdetto di Google: app dallo store, telefono
  integro). Sfide monouso legate a persona e accesso. Modalità: `off` (sviluppo), `soft` (i voti
  da dispositivi non verificati pesano la metà), `required` (senza verifica non si vota).
- `/v1/config` dice modalità di verifica e link agli store, ed è raggiungibile anche dalle app
  troppo vecchie.
- **Intestazioni di sicurezza** su ogni risposta (anti-frame, CSP, nosniff, HSTS in
  staging/produzione).

Fatto (app e pannello):
- Pannello del voto: "Voti aggiornati ogni ora · ultimo alle 22:37", "La media compare da 5
  voti", segno discreto al posto della media quando non c'è ancora.
- Verifica del dispositivo silenziosa a ogni accesso (`@expo/app-integrity`); se non riesce
  l'app funziona comunque.
- Schermata **Aggiorna WearX** quando la versione è troppo vecchia (risposta 426 o versione
  minima nella configurazione), con il link allo store.
- Pannello staff: pagina **Voti sospetti** (segnale, pseudonimo del votante, quanti voti,
  stato) con **Ripristina i voti** per i falsi positivi (nel registro di audit).

Controlli di sicurezza:
- **Semgrep** in CI: regole di sicurezza della comunità fissate a una versione precisa (Python,
  FastAPI, JWT, SQLAlchemy, crittografia, JavaScript/TypeScript/React, segreti) più 7 regole di
  progetto (`.semgrep/wearx.yml`: niente chiavi segrete nelle app, niente variabili PUBLIC che
  sembrano segreti, TLS sempre verificato, niente redirect automatici verso indirizzi scelti
  dagli utenti, JWT sempre verificati, niente HTML grezzo nel pannello, `secrets` e non
  `random` per i codici). Ogni regola di progetto è provata su codice sbagliato. Risultato:
  0 problemi; 3 casi esaminati e annotati (SQL costante nelle migrazioni).
- **Fuzzing** dell'API con Schemathesis (4.357 richieste generate, con accesso): nessun errore
  del server.
- **Scansione ZAP** in CI: API avviata con dati di prova e accesso, scansione attiva
  dall'OpenAPI; rischi alti fanno fallire la CI, gli altri diventano avvisi.

Provato davvero (web 390×844, pannello staff, worker acceso): media pubblicata e orario
dell'ultimo aggiornamento su un fit votato, fit proprio con 3 voti, due votanti sospetti
trovati dal lavoro orario (8 voti sempre 70; 3 voti a 100 ai fit di una persona), pagina Voti
sospetti, schermata Aggiorna WearX con l'API che chiede la 9.0.0.

Verifiche: 366 test API (+16); 250 test app (+6); 12 test del pannello (+1); ruff, mypy, tsc
puliti; build del pannello ok.

Note e decisioni da confermare:
- Media e numero orari valgono per **tutti**, non solo per l'autore: altrimenti l'autore con un
  secondo account vedrebbe comunque le variazioni in tempo reale.
- **Soglie nuove**: la media da 5 voti (come negli Insight) e a gruppi di almeno 3 voti nuovi o
  cambiati. Un fit con 4 voti mostra "4 voti" senza media.
- Chi preme "Vota" senza muovere lo slider dà 70: chi lo fa su 30 fit in una settimana viene
  trattato come uno script e i suoi voti non contano. È una scelta voluta (non sta giudicando),
  ma si può alzare la soglia.
- L'attestazione vera si prova solo su un telefono con una build dell'app (seduta 25): oggi è
  coperta da test con una "Apple" e una "Google" di prova.
- ZAP gira solo su GitHub (non in questo ambiente). La prima scansione è partita nella seduta 23,
  dopo il guasto di GitHub Actions della sera del 5 ottobre: risultati e correzioni lì.
- Per la seduta 23: avviare l'API senza l'intestazione `server` (uvicorn `--no-server-header`).

Schermate: `docs/screens/seduta-22-hardening.png`.

Da fare in seduta 23: infrastruttura (Terraform, staging, segreti, osservabilità, rete isolata
del worker che visita i link, progetto EAS).

### Seduta 23 — 2026-10-05

Decisioni del fondatore: **Google Cloud Run** in Belgio (europe-west1, UE, vicino a Supabase in
Irlanda), foto su **Cloudflare R2** (giurisdizione UE), **Sentry** (regione UE) per gli errori,
account Expo nella seduta 25.

Fatto:
- **Container** (non-root, senza strumenti di build): una sola immagine per API, worker, worker
  dei link e migrazioni (cambia il comando); pannello staff in Next "standalone". Nessuna
  intestazione `server`. Nuovo job di CI: costruisce le immagini, migra un database vuoto, avvia
  API, worker e pannello come in staging e controlla salute, utente non-root, intestazioni,
  battito dei worker.
- **Worker dei link separato** (`LinkCheckSettings`, coda propria): visita i siti esterni con
  un'identità Google senza permessi e solo i segreti che usa (database, Redis, Safe Browsing,
  Sentry). Chiude il rischio residuo della seduta 21 (DNS rebinding): anche ingannando i
  controlli non troverebbe chiavi. Ogni componente in produzione parte solo con i **suoi**
  segreti.
- **Terraform** (`infra/terraform`, un progetto Google per ambiente): Cloud Run per API e
  pannello, worker pool sempre accesi per worker e worker dei link, job delle migrazioni lanciato
  a ogni deploy; Secret Manager con un segreto per voce e lettori minimi; identità separate per
  ogni servizio; **deploy da GitHub senza chiavi** (Workload Identity legata al repository e
  all'ambiente GitHub); registro delle immagini con pulizia automatica; bucket R2 UE.
- **Osservabilità**: log JSON per Cloud Logging collegati alla traccia della richiesta e con
  l'id richiesta; una riga per richiesta con percorso "modello" (`/v1/users/{nickname}`), esito
  e durata, senza IP, query o intestazioni; errori su Sentry ripuliti da intestazioni, corpo,
  utente e IP; `/healthz/workers` (battito ogni minuto). **Allarmi via email**: API giù, worker
  fermi, pannello giù, più di 5 errori 5xx in 5 minuti; **budget mensile** con avvisi al 50%,
  90% e alla spesa prevista oltre il 100%.
- **Deploy**: staging automatico dopo ogni CI verde su main (immagini, migrazioni, API, worker,
  pannello, prova finale); produzione solo a mano con la tua approvazione. Finché gli ambienti
  GitHub non sono configurati il deploy non fa nulla.
- **IP reale** dietro Google (ultimo valore di X-Forwarded-For; i precedenti li scrive chiunque).
- Play Integrity su Google Cloud con l'identità del servizio: **nessuna chiave** da custodire.
- **Sentry nell'app** (`@sentry/react-native` 7.11, la versione di Expo SDK 57): solo crash ed
  errori, niente utente, schermate, testi dei tocchi o console; negli indirizzi id e nickname
  diventano "…". Si accende con `EXPO_PUBLIC_SENTRY_DSN` (seduta 25).
- `docs/INFRA.md`: guida passo-passo per accendere staging e produzione, costi, segreti, cosa
  fare se arriva un allarme e come tornare alla versione precedente.

Controlli: Terraform confrontato campo per campo con la documentazione ufficiale del provider
Google v8.5 (245 campi; il controllo trova errori di battitura inseriti apposta), formattazione
come `terraform fmt`, Checkov (Terraform, Dockerfile, workflow: 0 problemi, 3 eccezioni
motivate), actionlint sui workflow, Semgrep 0. Container provati riproducendo i loro passi qui
(registro Docker bloccato in questo ambiente): pannello standalone avviato con le sue
intestazioni, API in modalità staging con HSTS e senza `server`, migrazioni su database vuoto,
entrambi i worker con il battito. `terraform validate` e la costruzione vera delle immagini
girano nella CI.

**Prima scansione ZAP** (attiva, con accesso, su tutta l'API): un problema vero, corretto — il
carattere "nullo" (`%00`) nella ricerca degli stili e nel feed faceva arrivare un errore del
server (500) invece di un rifiuto. Ora qualunque carattere nullo nell'indirizzo, nei parametri o
nel corpo JSON viene rifiutato subito con 422 (test aggiunto). Aggiunta l'intestazione
`Cross-Origin-Resource-Policy`. Il resto erano note informative (risposte 4xx attese, cache).
In CI: Terraform `validate` passato, immagini costruite e avviate come in staging, deploy di
staging che aspetta la configurazione.

Verifiche: 380 test API (+14); 254 test app (+4); 12 test del pannello; ruff, mypy, tsc puliti;
bundle Android con Sentry.

Note e decisioni da confermare:
- Staging con 0 istanze dell'API sempre pronte (primo accesso dopo una pausa più lento, ~2-3 s),
  produzione con 1. Costo stimato: staging ~25-30 $/mese, produzione ~35-40 $/mese.
- Redis su Upstash a piano fisso (~10 $/mese): il worker interroga Redis di continuo e il piano
  a consumo costerebbe di più.
- Il pannello staff gira anch'esso su Cloud Run (al posto di Vercel): un fornitore in meno.
- Sentry nel pannello staff non c'è (pochi utenti, errori visibili a chi lo usa).
- In questo ambiente non posso creare risorse vere né costruire le immagini: lo fa la CI e,
  con gli account, la guida.

Da fare in seduta 24: qualità (test end-to-end, test di carico, accessibilità, testi completi).
