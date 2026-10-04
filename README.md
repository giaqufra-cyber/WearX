# WearX

App iOS e Android per pubblicare outfit, dividerli per stile e ricevere voti anonimi da 1 a 100.
Specifica completa: documento "WearX — Specifica tecnica e architettura v0.1".
Avanzamento: [docs/SEDUTE.md](docs/SEDUTE.md).

## Struttura

```
apps/mobile/            App React Native (Expo SDK 57, Expo Router)
services/api/           API Python (FastAPI) + migrazioni del database (Alembic)
packages/design-tokens/ Colori, caratteri e misure del prototipo
.github/workflows/      CI
```

## Avvio in locale

Requisiti: Node 22, pnpm 10, Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker.

```bash
docker compose up -d                 # Postgres 16, Redis 7, MinIO
pnpm install

# API
cd services/api
uv sync
WEARX_MIGRATION_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/wearx \
  uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
uv run pytest                        # test su un database di test creato da zero

# App (in un altro terminale)
cd apps/mobile
EXPO_PUBLIC_API_URL=http://<IP-del-computer>:8000 npx expo start
```

Sul telefono si apre con Expo Go per le schermate senza moduli nativi aggiuntivi; dalla seduta
in cui servono moduli nativi si usa una development build (`eas build --profile development`).

## Regole del progetto

- L'app non scrive mai direttamente nel database: tutto passa dall'API.
- Lo schema del database si cambia solo con una nuova migrazione Alembic, mai a mano.
- Nessun segreto nel repository: le variabili stanno in `.env` locale o nel secret manager.
- Ogni pull request deve passare la CI (lint, tipi, test, bundle).
