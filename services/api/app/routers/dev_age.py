"""Pagina "del fornitore" per il fornitore finto. Solo sviluppo e test: in produzione
questo router non viene montato (e il fornitore finto è vietato dalla configurazione).

Si apre dal telefono durante la verifica: si sceglie l'esito, la pagina invia un webhook
firmato all'API (lo stesso percorso di un fornitore vero) e riporta all'app.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.age.fake import FakeAgeProvider
from app.db import get_session
from app.routers.age import _valid_return_url, apply_webhook

router = APIRouter(prefix="/v1/dev/fake-age", include_in_schema=False)

Session = Annotated[AsyncSession, Depends(get_session)]

CHOICES = {
    "adult": ("Ho 18 anni o più", "18_plus", 25),
    "minor": ("Ho 16 o 17 anni", "16_17", 17),
    "under16": ("Ho meno di 16 anni", "under_16", 14),
    "cancel": ("Annulla", None, None),
}

PAGE = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verifica dell'età (prova)</title>
<style>
body{{margin:0;background:#0A0A0B;color:#F2EFE9;font:16px/1.5 system-ui,sans-serif;
padding:32px 20px}}
h1{{font:500 30px/1.1 Georgia,serif;margin:0 0 8px}} p{{color:#A3A09A;margin:0 0 24px}}
.tag{{font:11px monospace;letter-spacing:.14em;color:#FFB547;border:1px solid #FFB547;
border-radius:99px;padding:4px 10px;display:inline-block;margin-bottom:18px}}
button{{display:block;width:100%;height:52px;margin:0 0 12px;border-radius:99px;
font:700 15px system-ui;
border:1px solid #3A3A40;background:transparent;color:#F2EFE9}}
button.main{{background:#D7FF3A;color:#0A0A0B;border:0}}
</style></head><body>
<span class="tag">FORNITORE DI PROVA · SOLO SVILUPPO</span>
<h1>Verifica dell'età</h1>
<p>Metodo: {method}. Qui un fornitore vero farebbe la verifica. Scegli l'esito da simulare.</p>
<form method="post">
<input type="hidden" name="return_url" value="{return_url}">
{buttons}
</form></body></html>"""


@router.get("/{ref}", response_class=HTMLResponse)
async def fake_page(ref: str, method: str = "", return_url: str = "") -> HTMLResponse:
    if not _valid_return_url(return_url):
        return HTMLResponse("Indirizzo di ritorno non ammesso", status_code=422)
    buttons = "\n".join(
        f'<button name="choice" value="{key}" class="{"main" if key == "adult" else ""}">'
        f"{html.escape(label)}</button>"
        for key, (label, _, _) in CHOICES.items()
    )
    return HTMLResponse(
        PAGE.format(
            method=html.escape(method), return_url=html.escape(return_url), buttons=buttons
        ),
        headers={
            "content-security-policy": (
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                "frame-ancestors 'none'"
            )
        },
    )


@router.post("/{ref}", response_model=None)
async def fake_submit(
    ref: str,
    session: Session,
    choice: Annotated[str, Form()],
    return_url: Annotated[str, Form()],
    method: str = "",
) -> RedirectResponse | HTMLResponse:
    if choice not in CHOICES or not _valid_return_url(return_url):
        return HTMLResponse("Richiesta non valida", status_code=422)
    _, band, years = CHOICES[choice]
    provider = FakeAgeProvider()
    if band is None:
        body, headers = provider.build_webhook(ref, "cancelled")
    else:
        # I metodi con documento danno la data di nascita; la stima con selfie solo la fascia.
        birth = None
        if method in ("id_document", "spid", "cie") and years is not None:
            birth = datetime.now(UTC).date() - timedelta(days=years * 365 + 120)
        body, headers = provider.build_webhook(ref, "passed", age_band=band, birth_date=birth)
    await apply_webhook(session, provider, headers, body)
    separator = "&" if "?" in return_url else "?"
    return RedirectResponse(f"{return_url}{separator}result={quote(choice)}", status_code=303)
