#!/usr/bin/env bash
# WearX demo da aprire sul telefono: tutto gira su questo computer, dietro UN link https.
#
#   scripts/demo.sh                 # con il link pubblico (Cloudflare, gratis, cambia a ogni avvio)
#   scripts/demo.sh --senza-tunnel  # solo su questo computer: http://localhost:8090
#
# Serve: Docker (Postgres e Redis), Node 22 + pnpm, uv, cloudflared. Guida: docs/DEMO.md.
# Solo per provare l'app: accesso finto (codice sempre 123456), dati di prova azzerati a ogni avvio.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${DEMO_PORT:-8090}"
TUNNEL=1
[ "${1:-}" = "--senza-tunnel" ] && TUNNEL=0

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Manca '$1': $2 (vedi docs/DEMO.md)"; exit 1; }
}
need docker "installa Docker Desktop e attiva l'integrazione con WSL"
need pnpm "sudo npm install -g pnpm@10"
need uv "curl -LsSf https://astral.sh/uv/install.sh | sh"
need cc "sudo apt install -y build-essential"
if [ "$TUNNEL" = 1 ]; then need cloudflared "installa cloudflared (pacchetto .deb da GitHub)"; fi

cd "$ROOT"
echo "1/4 Database e Redis (Docker)…"
docker compose up -d postgres redis >/dev/null
for _ in $(seq 1 60); do
  docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done

echo "2/4 Dipendenze…"
[ -d node_modules ] || pnpm install --frozen-lockfile
(cd services/api && uv sync --quiet)

DIST="apps/mobile/dist-demo"
if [ ! -f "$DIST/index.html" ] || [ -n "$(find apps/mobile/src apps/mobile/app.json packages -newer "$DIST/index.html" -type f -print -quit)" ]; then
  echo "3/4 Preparo l'app web della demo (qualche minuto la prima volta)…"
  (cd apps/mobile && EXPO_PUBLIC_DEMO=1 npx expo export --clear --platform web --output-dir dist-demo >/dev/null)
else
  echo "3/4 App web della demo già pronta."
fi

URL="http://localhost:$PORT"
if [ "$TUNNEL" = 1 ]; then
  echo "4/4 Apro il link pubblico (Cloudflare)…"
  LOG="$(mktemp)"
  cloudflared tunnel --no-autoupdate --url "http://localhost:$PORT" >"$LOG" 2>&1 &
  CF=$!
  trap 'kill $CF 2>/dev/null || true; rm -f "$LOG"' EXIT
  URL=""
  for _ in $(seq 1 60); do
    URL="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1 || true)"
    [ -n "$URL" ] && break
    if ! kill -0 "$CF" 2>/dev/null; then cat "$LOG"; exit 1; fi
    sleep 1
  done
  if [ -z "$URL" ]; then
    echo "Cloudflare non ha dato un link entro un minuto. Riprova tra poco."
    cat "$LOG"
    exit 1
  fi
else
  echo "4/4 Senza tunnel: la demo è raggiungibile solo da questo computer."
fi

echo "Avvio WearX (database nuovo e dati di prova, circa mezzo minuto)…"
cd services/api
DEMO_PUBLIC_URL="$URL" DEMO_PORT="$PORT" uv run python -m tests.demo_target
