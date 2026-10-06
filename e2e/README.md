# Percorsi end-to-end (seduta 24)

Provano WearX come una persona vera, dall'inizio alla fine, su tutto il sistema: app web,
API, worker delle foto, database, Redis e archivio. Solo i servizi esterni sono sostituiti da
copie di prova: Supabase Auth (il codice di conferma è sempre `123456`), il fornitore di
verifica dell'età e il controllo delle password violate.

| Percorso | Cosa prova |
|----------|------------|
| `registrazione.spec.ts` | account → codice → verifica dell'età → tipo di profilo → stili → feed |
| `voto.spec.ts` | voto con conferma dello stile; numero e media dopo l'aggiornamento orario |
| `pubblica.spec.ts` | foto dalla galleria → stile → capo → pubblicazione → elaborazione nel worker → portfolio |
| `seguire.spec.ts` | account privato: richiesta → notifica → accetta → portfolio visibile |
| `moderazione.spec.ts` | segnalazione → decisione dello staff → avviso a chi ha pubblicato → reclamo |

## In locale

```bash
# Postgres e Redis accesi (docker compose up -d postgres redis)
cd apps/mobile
EXPO_PUBLIC_API_URL=http://localhost:8000 EXPO_PUBLIC_SUPABASE_URL=http://localhost:54321 \
  EXPO_PUBLIC_EMAIL_OTP=1 npx expo export --platform web --output-dir dist-e2e
cd ../../e2e
npx playwright install chromium   # la prima volta
./run-local.sh                    # ambiente da zero + tutti i percorsi
```

`run-local.sh` avvia `services/api/tests/e2e_target.py` (database nuovo a ogni esecuzione),
aspetta che sia pronto, esegue i test e lo spegne. Per guardare l'app a mano: avvia solo
`cd services/api && uv run python -m tests.e2e_target` e apri http://localhost:8081
(persone di prova: `giulia@e2e.test`, `marco@e2e.test`, password `Fit-di-prova-2026!`).

## Sul telefono (Maestro)

Gli stessi percorsi per iOS e Android sono in `apps/mobile/.maestro/`. Servono una build di
sviluppo dell'app (seduta 25) con `EXPO_PUBLIC_API_URL` e `EXPO_PUBLIC_SUPABASE_URL` che puntano
all'ambiente E2E sul computer, e la [CLI di Maestro](https://maestro.dev):

```bash
maestro test -e EMAIL=nuova.$(date +%s)@e2e.test -e NICK=nuova.$(date +%s) apps/mobile/.maestro
```

Non sono ancora stati eseguiti su un telefono: la prima esecuzione è prevista nella seduta 25.
