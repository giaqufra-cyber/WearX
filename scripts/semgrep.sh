#!/usr/bin/env bash
# Analisi statica di sicurezza (seduta 22): regole di sicurezza della comunità Semgrep, fissate a
# una versione precisa (stesso risultato in locale e in CI), più le regole di progetto in
# .semgrep/wearx.yml. Esce con errore se trova qualcosa; in CI i risultati diventano annotazioni.
#
# Regole escluse dopo revisione (falsi positivi per come è scritto il codice):
# - python.sqlalchemy.security.audit.avoid-sqlalchemy-text: usiamo text() SEMPRE con parametri
#   (:nome); il testo SQL è composto solo da costanti del modulo (controllato anche da ruff S608).
set -euo pipefail

RULES_COMMIT="a84ff9cc2453ca91d581380de4b8b3f272f6f4be"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="${SEMGREP_RULES_DIR:-$ROOT/.semgrep-cache/rules}"

if [ ! -d "$CACHE/.git" ] || [ "$(git -C "$CACHE" rev-parse HEAD)" != "$RULES_COMMIT" ]; then
  rm -rf "$CACHE"
  git init -q "$CACHE"
  git -C "$CACHE" fetch -q --depth 1 https://github.com/semgrep/semgrep-rules "$RULES_COMMIT"
  git -C "$CACHE" checkout -q FETCH_HEAD
fi
rm -f "$CACHE/python/sqlalchemy/security/audit/avoid-sqlalchemy-text.yaml"

CONFIGS=(
  python/lang/security python/fastapi python/jwt python/sqlalchemy/security python/cryptography
  javascript/lang/security javascript/browser/security javascript/jsonwebtoken
  typescript/react/security typescript/lang/security generic/secrets
)
ARGS=()
for c in "${CONFIGS[@]}"; do ARGS+=(--config "$CACHE/$c"); done

OUT="${SEMGREP_OUT:-$ROOT/.semgrep-cache/results.json}"
cd "$ROOT"
semgrep scan --metrics=off --quiet --disable-version-check \
  "${ARGS[@]}" --config .semgrep/wearx.yml \
  --exclude node_modules --exclude .next --exclude "schema.ts" --exclude "*.test.*" \
  --exclude "services/api/tests" \
  --json -o "$OUT" \
  services/api/app services/api/migrations apps/mobile/src apps/admin/src packages .github || true

python3 - "$OUT" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
for err in data.get("errors", []):
    print(f"::error title=semgrep::{err.get('message', err)}")
results = data.get("results", [])
for r in results:
    rule = r["check_id"].split(".")[-1]
    msg = " ".join(r["extra"]["message"].split())[:500]
    print(f"::error file={r['path']},line={r['start']['line']},title={rule}::{msg}")
print(f"Semgrep: {len(results)} risultati, {len(data.get('errors', []))} errori")
sys.exit(1 if results or data.get("errors") else 0)
PY
