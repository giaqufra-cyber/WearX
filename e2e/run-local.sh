#!/usr/bin/env bash
# Avvia l'ambiente E2E da zero (database nuovo), esegue i percorsi e lo spegne.
# Prima: Postgres e Redis accesi; app web esportata in apps/mobile/dist-e2e (vedi README.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/services/api"
rm -f e2e-ready.json
uv run python -m tests.e2e_target > /tmp/wearx-e2e.log 2>&1 &
TARGET=$!
trap 'kill $TARGET 2>/dev/null || true' EXIT
for _ in $(seq 1 90); do
  [ -f e2e-ready.json ] && break
  if ! kill -0 $TARGET 2>/dev/null; then cat /tmp/wearx-e2e.log; exit 1; fi
  sleep 1
done
if [ "${WEARX_E2E_ADMIN:-0}" = "1" ]; then
  # Pannello dello staff in sviluppo, con l'accesso a token (mai in produzione).
  cd "$ROOT/apps/admin"
  NEXT_PUBLIC_API_URL=http://localhost:8000 NEXT_PUBLIC_ADMIN_DEV_LOGIN=1 \
    npx next dev -p 3000 > /tmp/wearx-e2e-admin.log 2>&1 &
  ADMIN=$!
  trap 'kill $TARGET $ADMIN 2>/dev/null || true' EXIT
  for _ in $(seq 1 90); do
    curl -sf -o /dev/null http://localhost:3000/ && break
    sleep 1
  done
  PROJECTS=()
else
  PROJECTS=(--project app)
fi
cd "$ROOT/e2e"
npx playwright test "${PROJECTS[@]}" "$@"
