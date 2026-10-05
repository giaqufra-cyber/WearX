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
