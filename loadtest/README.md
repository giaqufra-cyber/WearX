# Test di carico (k6)

Persone finte che fanno quello che fa una persona vera: scorrono il feed di uno dei loro stili,
aprono un fit, votano (se non l'hanno già fatto), guardano un profilo, con pause di qualche
secondo tra un'azione e l'altra. Ogni utente virtuale ha un account suo.

```bash
cd services/api && uv run python -m tests.load_target 200     # API + 200 persone, ~500 fit, ~12.600 voti
k6 run -e USERS=$PWD/services/api/load-users.json -e VUS=200 -e DURATION=90s loadtest/api.js
```

Variabili: `VUS` (persone in contemporanea, 50), `DURATION` (2m), `THINK` (1 = pause vere,
0 = prova di stress senza pause), `API` (indirizzo), `P95_FEED`/`P95_POST`/`P95_VOTE`/`P95_USER`
(soglie in ms). La CI lo lancia a ogni modifica con 100 persone per 90 secondi (job `load`).

Soglie: meno dell'1% di errori, 95% delle risposte entro 400 ms (feed), 250 ms (fit),
300 ms (voto e profilo).

## Risultati (seduta 24)

Un solo processo dell'API (= un'istanza Cloud Run da 1 vCPU), su una macchina da 2 vCPU divisa
con Postgres e k6 stesso: i numeri veri in Cloud Run saranno simili o migliori.

| Persone in contemporanea | Richieste/s | p95 feed | p95 fit | p95 voto | Errori |
|---|---|---|---|---|---|
| 50 | 23 | 32 ms | 18 ms | 32 ms | 0 |
| 200 | 88 | 264 ms | 206 ms | 277 ms | 0 |
| 400 (saturazione) | 118 | 2,3 s | 2,3 s | 2,3 s | 0 |

Prima delle due correzioni della seduta 24, a 200 persone: p95 feed 1,2 s, voto 950 ms.

1. **Firma degli URL delle foto** (era il 21% del tempo della CPU): ora si calcola con una
   funzione nostra (12 volte più veloce di boto3, risultato identico, verificato nei test) e
   l'URL di una foto resta lo stesso per un quarto d'ora. Bonus: l'app ritrova la foto nella sua
   cache invece di riscaricarla.
2. **Meno connessioni al database per istanza** (da 10+10 a 3+2): con meno richieste che si
   contendono il database insieme, ognuna finisce prima. Serve anche al pooler di Supabase.

Il resto del tempo è lavoro "giusto": TLS verso il database, verifica dei token, query.
Con la prova di stress senza pause, gli errori che compaiono sono 429: i limiti per persona
(600 feed all'ora, 40 voti al minuto) che fanno il loro lavoro.
