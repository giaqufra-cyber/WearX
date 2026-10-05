"""Risultati della scansione ZAP come annotazioni della CI (seduta 22).

Rischio alto: la CI fallisce. Medio e basso: avvisi da guardare. Informativi: note.
Gli avvisi già esaminati e accettati stanno in .zap/accepted.tsv (id della regola e motivo).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
accepted = {}
accepted_file = Path(__file__).with_name("accepted.tsv")
for line in accepted_file.read_text().splitlines():
    if line.strip() and not line.startswith("#"):
        rule, _, reason = line.partition("\t")
        accepted[rule.strip()] = reason.strip()

high = 0
for site in report.get("site", []):
    for alert in site.get("alerts", []):
        rule = str(alert.get("pluginid"))
        risk = int(alert.get("riskcode", 0))
        name = alert.get("name", "?")
        uris = sorted({i.get("method", "") + " " + i.get("uri", "") for i in alert.get("instances", [])})
        where = "; ".join(uris[:5]) + (f" (+{len(uris) - 5})" if len(uris) > 5 else "")
        if rule in accepted:
            print(f"::notice title=ZAP {rule} accettato::{name} — {accepted[rule]}")
            continue
        level = {3: "error", 2: "warning", 1: "warning"}.get(risk, "notice")
        high += risk == 3
        print(f"::{level} title=ZAP {rule} {alert.get('riskdesc', '')}::{name} — {where}")
print(f"ZAP: {high} avvisi ad alto rischio")
sys.exit(1 if high else 0)
