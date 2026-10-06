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
cd "$ROOT/e2e"
npx playwright test "$@"
