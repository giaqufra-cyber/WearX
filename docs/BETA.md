# WearX: la beta (TestFlight e Google Play)

Guida passo-passo (seduta 25). Le build dell'app le prepara **EAS** (i server di Expo): niente Mac
né Android Studio sul tuo computer. Da GitHub si lancia tutto con un pulsante.

> **Regola d'oro sui segreti** (come in `docs/INFRA.md`): chiavi Apple (.p8), file JSON di
> Google, token di Expo e di Sentry li carichi **tu** direttamente su expo.dev o su GitHub.
> Mai in chat, mai nel repository.

## Prima della beta: cosa deve già funzionare

La beta usa lo **staging**. Senza questi punti i tester installano l'app ma non riescono a
registrarsi:
1. Staging acceso (`docs/INFRA.md`, passi 1-5): l'app deve avere un indirizzo `https://` dell'API.
2. **Dominio ed email (SMTP)** su Supabase: senza, Supabase non manda il codice di conferma a
   nessuno fuori dal team del progetto.
3. Le pagine legali raggiungibili (lo sono già, dall'API: servono ad Apple e Google).

## Decisione: account personali o di un'azienda?

| | Personale | Organizzazione (azienda) |
|---|---|---|
| Apple (99 $/anno) | Nome e cognome come venditore sullo store | Serve una società e il numero D-U-N-S (gratis, 1-2 settimane) |
| Google Play (25 $ una volta) | Prima della pubblicazione: **test chiuso con almeno 12 tester per 14 giorni di fila** | Nessun obbligo di test chiuso |

**Consiglio:** account personali adesso. I 12 tester per 14 giorni con la tua associazione non
sono un problema, e il test chiuso è comunque la beta che vogliamo fare. Se più avanti apri una
società, le app si trasferiscono all'account dell'azienda (Apple e Google lo prevedono).

## Costi

Apple 99 $/anno · Google Play 25 $ una volta · Expo gratuito (15 build Android e 15 iOS al mese,
in coda a bassa priorità: di solito 10-30 minuti) · Sentry gratuito.

## 1. Account (una volta)

1. **Apple Developer Program**: developer.apple.com/programs → iscrizione con il tuo Apple ID
   (con autenticazione a due fattori). L'approvazione può richiedere fino a 48 ore.
2. **Google Play Console**: play.google.com/console → account personale, verifica d'identità
   con documento. Anche qui qualche giorno.
3. **Expo**: expo.dev → crea un account (gratuito) e un progetto chiamato `wearx`.
   **Mandami** (non sono segreti): il nome del tuo account Expo e l'**ID del progetto**
   (Project settings → ID). Li scrivo io in `app.json`.

## 2. Il progetto sugli store

- **App Store Connect** → App → "+" → Nuova app: piattaforma iOS, nome `WearX`, lingua Italiano,
  bundle ID `app.wearx.mobile` (se non compare: developer.apple.com → Identifiers → "+"), SKU
  `wearx`. **Mandami** l'**Apple ID dell'app** (un numero, in Informazioni app): va in `eas.json`
  per l'invio automatico a TestFlight.
- **Google Play Console** → Crea app: nome `WearX`, app, gratuita. Compila le sezioni richieste
  usando `docs/STORE.md` (contenuti, sicurezza dei dati, classificazione, pubblico di destinazione:
  16-17 e 18+).

## 3. Collegare GitHub a Expo

expo.dev → Account settings → Access tokens → "Create token" (nome `github`). Poi su GitHub:
repository WearX → Settings → Secrets and variables → Actions → **New repository secret**:
nome `EXPO_TOKEN`, valore il token. (È un segreto: incollalo solo lì.)

## 4. Variabili dell'app su expo.dev

expo.dev → progetto wearx → **Environment variables** → ambiente **preview** (per la beta):

| Nome | Valore | Visibilità |
|---|---|---|
| `EXPO_PUBLIC_API_URL` | indirizzo dell'API di staging (output di Terraform `api_url`) | Plain text |
| `EXPO_PUBLIC_SUPABASE_URL` | `https://alcpqfphwygpktrcyauu.supabase.co` | Plain text |
| `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | la chiave `sb_publishable_...` (pubblica) | Plain text |
| `EXPO_PUBLIC_SENTRY_DSN` | DSN del progetto Sentry `wearx-app` | Plain text |
| `SENTRY_AUTH_TOKEN` | Sentry → Settings → Auth Tokens (permesso "project:releases") | **Secret** |

L'ambiente **production** si compila uguale, con l'API di produzione, prima del lancio.
Una build per gli store senza `EXPO_PUBLIC_API_URL` in https si ferma subito (controllo in
`app.config.ts`): meglio un errore che un'app che non si collega.

## 5. Credenziali Apple (una volta, 10 minuti, dal tuo computer)

Serve Node.js (nodejs.org, versione LTS). Nel terminale, dentro la cartella del progetto:

```bash
cd apps/mobile
npx eas-cli login
npx eas-cli credentials --platform ios
```

Scegli il profilo `beta`, accedi con il tuo Apple ID quando lo chiede e lascia che EAS crei
tutto (certificato, profilo, **chiave per le notifiche push**, chiave API di App Store Connect
per l'invio a TestFlight). Le credenziali restano su Expo: da lì in poi le build partono da
GitHub senza di te.

## 6. Credenziali Google (una volta)

1. **Prima build Android:** GitHub → Actions → "App (build per i tester e gli store)" → Run
   workflow con profilo `beta`, piattaforma `android`, **invio disattivato**. Quando è pronta,
   da expo.dev scarica il file `.aab`.
2. **Primo caricamento a mano** (Google lo pretende la prima volta): Play Console → Test →
   Test interno → Crea release → carica il `.aab`.
3. **Chiave per l'invio automatico:** Google Cloud (progetto `wearx-staging` va bene) → IAM →
   Account di servizio → crea `play-submit` → Chiavi → Aggiungi chiave JSON (si scarica sul tuo
   computer). Play Console → Utenti e autorizzazioni → Invita l'email dell'account di servizio
   con il permesso di rilasciare nei test. Poi expo.dev → progetto → Credentials → Android →
   **Google Service Account Key** → carica il JSON (anche per le notifiche push: "FCM V1").
   Il file JSON poi cancellalo dal computer.

## 7. Ogni nuova beta

GitHub → Actions → **"App (build per i tester e gli store)"** → Run workflow:
- profilo `beta`, piattaforma `all`, invio **attivo**.

Il workflow controlla l'app (tipi e test), avvia le build su Expo e, quando sono pronte, le manda
da solo a **TestFlight** e al **test interno di Google Play**. Il numero di build sale da solo.
Per la **produzione** il profilo è `production` e GitHub chiede la tua approvazione.

## 8. I tester

**iPhone (TestFlight)**
- *Interni* (fino a 100, devono essere utenti del tuo App Store Connect): subito.
- *Esterni* (fino a 10.000, con un **link pubblico**): la prima build passa una revisione di
  Apple (di solito 1-2 giorni). Servono: descrizione della beta, email per i feedback, link
  all'informativa privacy (`<API_URL>/legal/privacy`) e un **account di prova** per i revisori
  (crealo sullo staging e scrivi email e password nel modulo di App Store Connect).
- Le build di TestFlight scadono dopo 90 giorni.

**Android (Google Play)**
- *Test interno* (fino a 100 email): subito, senza revisione. Ideale per i primi 10-20.
- *Test chiuso* (lista di email o un Google Group): quello che conta per i 12 tester x 14 giorni.
  Consiglio: un Google Group "WearX beta" a cui si iscrivono i soci che vogliono provare.
- Per un APK da installare a mano (senza Play): profilo `preview`, piattaforma `android`.

**Cosa dire ai tester:** hanno almeno 16 anni; WearX è in prova e alcuni dati potrebbero essere
cancellati; per segnalare problemi c'è **Profilo → Privacy e sicurezza → Segnala un problema**
(i messaggi arrivano nella pagina **Feedback** del pannello dello staff).

### Cosa chiedere di provare (prima settimana)

1. Registrazione completa, verifica dell'età, scelta degli stili.
2. Votare almeno 20 fit; pubblicarne almeno 2 con capi e link.
3. Seguire e farsi seguire (profilo privato e Business).
4. Segnalare un fit di prova; ricevere le notifiche.
5. Scaricare i propri dati; provare "Cancella l'account" e tornare indietro.

## 9. Test automatici sul telefono

- **Android:** il workflow **"App su Android (Maestro)"** installa l'app vera su un emulatore e
  ripete registrazione, voto, pubblicazione e follow a ogni modifica dell'app (e ogni lunedì).
  Schermate e registri sono negli artefatti del workflow.
- **iPhone:** gli stessi flussi (`apps/mobile/.maestro`) richiedono un Mac; per la beta bastano
  le prove a mano su TestFlight (punto 8).

## Lato server per la beta (dalla lista "Prima di far provare l'app ad altri")

Team ID Apple in `WEARX_APPLE_TEAM_ID` (App Attest), progetto Google collegato a Play Console per
Play Integrity, `WEARX_PUSH_PROVIDER=expo` con il token di Expo per i push sul server
(`WEARX_EXPO_ACCESS_TOKEN`), link agli store per la schermata "Aggiorna WearX".
