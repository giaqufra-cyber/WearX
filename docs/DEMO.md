# WearX: la demo da provare sul telefono

Per **vedere e usare** WearX su iPhone (o Android) senza account Apple a pagamento, senza store e
senza server nel cloud. Tutto gira sul tuo computer; il telefono ci arriva con un link https.

> È una demo: accesso finto (il codice di conferma è sempre `123456`), nessuna email, dati di
> prova che si azzerano a ogni avvio, niente notifiche push. Non è la beta per i tester
> (quella è `docs/BETA.md`).

Due modi di aprirla, con la stessa demo accesa sul computer:

| | Come | Costo | Limiti |
|---|---|---|---|
| **Safari** | link o QR → "Aggiungi alla schermata Home" | 0 € | non è nativa: scorrimento e animazioni sono quelli del browser |
| **App iPhone** | `.ipa` da GitHub, installato con Sideloadly | 0 € | va reinstallata ogni 7 giorni; max 3 app con Apple ID gratuito |

## 1. Preparare il computer (una volta, Windows)

1. **Ubuntu dentro Windows.** PowerShell come amministratore: `wsl --install`, riavvia, crea
   l'utente di Ubuntu. Da qui in poi i comandi vanno nella finestra "Ubuntu".
2. **Docker Desktop** (docker.com) → Settings → Resources → **WSL integration** → Ubuntu attivo.
3. **Strumenti in Ubuntu** (una riga alla volta):
   ```bash
   sudo apt install -y build-essential   # compilatore: una libreria dei test va compilata
   curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
   sudo npm install -g pnpm@10
   curl -LsSf https://astral.sh/uv/install.sh | sh
   curl -L -o cf.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && sudo dpkg -i cf.deb
   git clone https://github.com/giaqufra-cyber/wearx && cd wearx && pnpm install
   ```
   Chiudi e riapri Ubuntu dopo l'installazione di uv (aggiunge il comando al terminale).

Su Mac o Linux gli stessi strumenti (Docker, Node 22, pnpm, uv, cloudflared) bastano.

## 2. Accendere la demo (ogni volta)

```bash
cd ~/wearx
git pull            # l'ultima versione
scripts/demo.sh
```

La prima volta ci mette qualche minuto (prepara l'app web). Poi stampa:
- il **link** `https://….trycloudflare.com` (cambia a ogni avvio);
- un **QR per l'app** WearX Demo e un **QR per Safari**;
- l'accesso pronto: **`ospite@demo.test`** / **`Demo-WearX-2026!`**.

Lascia la finestra aperta: chiuderla (o Ctrl+C) spegne la demo. Il computer deve restare acceso
e collegato a internet.

Cosa trovi dentro: 8 persone, 18 fit disegnati in 6 stili con capi e prezzi, voti già dati (le
medie si aggiornano ogni minuto invece che ogni ora), un follow accettato, una richiesta inviata e
una ricevuta. Puoi registrarti con un account nuovo (verifica dell'età di prova inclusa),
pubblicare fit dalla galleria, votare, seguire, segnalare.

## 3a. Su Safari (iPhone, iPad, qualsiasi telefono)

Inquadra il secondo QR con la Fotocamera (o apri il link). Poi **Condividi → Aggiungi alla
schermata Home**: si apre a tutto schermo come un'app.

## 3b. L'app vera sull'iPhone (Sideloadly, gratis)

**Una volta:**
1. Su Windows installa **Sideloadly** (sideloadly.io) e **iTunes e iCloud scaricati dal sito
   Apple** (non dal Microsoft Store).
2. Crea un **Apple ID secondario** gratuito, solo per questo: Sideloadly ti chiede la password.
3. Sull'iPhone: Impostazioni → Privacy e sicurezza → **Modalità sviluppatore** (la voce compare
   dopo il primo tentativo di installazione), attiva e riavvia.

**Ogni 7 giorni (o quando vuoi la versione nuova):**
1. GitHub → **Actions** → **"App iPhone per Sideloadly"** → **Run workflow** (ramo `main`).
   Dopo circa 20-30 minuti, in fondo alla pagina della build: artefatto **WearX-demo-iphone** →
   scarica lo zip ed estrai `WearX-demo.ipa`.
2. iPhone collegato via cavo al computer, sblocca e tocca **Autorizza**.
3. Sideloadly: trascina `WearX-demo.ipa`, scrivi l'Apple ID secondario, **Start**.
4. Prima apertura: Impostazioni → Generali → **VPN e gestione dispositivi** → autorizza il tuo
   Apple ID.

**Usarla:** accendi la demo sul computer, apri **WearX Demo** e inquadra il **primo QR** con la
Fotocamera dell'iPhone (apre l'app già collegata), oppure incolla il link nella schermata
"Collega la demo". Se il link è cambiato l'app te lo chiede di nuovo; dalla schermata "Non
riusciamo a raggiungere WearX" c'è **Cambia server della demo**.

Cosa non c'è nella build demo: notifiche push e verifica del dispositivo (App Attest), che un
Apple ID gratuito non può firmare. Il resto è l'app vera, con lo stesso codice di TestFlight.

## Se qualcosa non va

| Problema | Soluzione |
|---|---|
| `Manca 'docker'` o errore di Docker | Docker Desktop aperto, con WSL integration attiva per Ubuntu |
| La porta 5432 è occupata | un altro Postgres acceso sul computer: spegnilo, oppure `docker compose down` e riprova |
| Cloudflare non dà un link | rete aziendale/universitaria che blocca i tunnel: riprova da casa o con l'hotspot del telefono |
| L'app dice che il server non risponde | la demo è spenta o il link è cambiato: usa il QR nuovo |
| Sideloadly: errore sull'Apple ID | password dell'Apple ID secondario, oppure attiva la verifica in due passaggi e riprova |
| Sideloadly: "maximum number of apps" | l'Apple ID gratuito ha già 3 app: cancellane una dall'iPhone |
| Dopo 7 giorni l'app non si apre | normale con l'Apple ID gratuito: reinstalla con Sideloadly (punto 3b) |

## Come funziona (per chi sviluppa)

- `scripts/demo.sh` → `services/api/tests/demo_target.py`: riusa l'ambiente dei test end-to-end
  (`tests/e2e_target.py`: database nuovo, archivio S3 finto, accesso finto, worker) e mette tutto
  dietro la porta 8090: `/auth/v1/*` accesso finto, `/<bucket>/*` foto, `/v1`, `/legal`, `/r`,
  `/healthz` API, il resto app web (`apps/mobile/dist-demo`). Cloudflare pubblica la porta 8090.
- App con `EXPO_PUBLIC_DEMO=1`: sul web API e accesso sono l'indirizzo della pagina; sul telefono
  il server si sceglie a runtime (`src/features/demo`, link `wearx://demo?server=…`); niente
  App Attest né push; codice di conferma a 6 cifre. `app.config.ts` dà alla build demo nome e
  identificativo propri (`WearX Demo`, `app.wearx.mobile.demo`) e toglie gli entitlement a
  pagamento.
- La build demo non va mai negli store: i profili EAS non impostano `EXPO_PUBLIC_DEMO`.
