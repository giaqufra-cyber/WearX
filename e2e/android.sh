#!/usr/bin/env bash
# Percorsi Maestro sull'emulatore Android (seduta 25). Lo lancia la CI dentro l'emulatore
# (workflow "App su Android (Maestro)"), con l'ambiente E2E già acceso su questo computer:
# per l'emulatore questo computer è 10.0.2.2.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APK="$ROOT/apps/mobile/android/app/build/outputs/apk/release/app-release.apk"
OUT="$ROOT/e2e/android-results"
mkdir -p "$OUT"

adb wait-for-device
# Chrome senza le schermate di benvenuto (la verifica dell'età di prova si apre lì).
adb shell 'echo "chrome --disable-fre --no-default-browser-check --no-first-run" > /data/local/tmp/chrome-command-line'
adb shell am set-debug-app --persistent com.android.chrome || true
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0
adb install -r "$APK"
# Notifiche: si concede il permesso subito (la richiesta di sistema interromperebbe i percorsi).
adb shell pm grant app.wearx.mobile android.permission.POST_NOTIFICATIONS || true

cd "$OUT"
set +e
"$HOME/.maestro/bin/maestro" test "$ROOT/apps/mobile/.maestro" \
  --format junit --output "$OUT/report.xml" --debug-output "$OUT/debug" 2>&1 | tee "$OUT/maestro.log"
status=${PIPESTATUS[0]}
set -e
adb exec-out screencap -p > "$OUT/ultima-schermata.png" || true
adb logcat -d -t 2000 > "$OUT/logcat.txt" || true
exit $status
