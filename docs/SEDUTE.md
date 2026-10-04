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
| 22 | Hardening | Attestazione dispositivo, anti-abuso voti, Semgrep, scansione ZAP | — |
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
