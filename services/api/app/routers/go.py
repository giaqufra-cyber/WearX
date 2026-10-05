"""Redirect dei link ai negozi: /r/<codice firmato> (seduta 21).

Si apre dal browser interno dell'app, senza accesso: il codice firmato dice quale link, di
quale fit e quale capo. Al momento del clic:
- link bloccato (sito pericoloso o dominio bloccato): pagina che spiega e NON prosegue;
- altrimenti: conta il clic (sul link e sul fit) e porta al negozio. Per i siti verificati di
  un account Business si aggiunge utm_source=wearx (il negozio vede che il clic arriva da qui).
Nessun dato di chi clicca viene salvato qui (i click per gli Insight sono gli eventi dell'app).
"""

from __future__ import annotations

import html
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.links import parse_go_token
from app.ratelimit import rate_limit

router = APIRouter(tags=["links"])

Session = Annotated[AsyncSession, Depends(get_session)]

_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-robots-tag": "noindex",
}

_PAGE = """<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · WearX</title>
<style>
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px;
         background: #0A0A0B; color: #F2EFE9;
         font: 16px/1.5 -apple-system, system-ui, sans-serif; }}
  main {{ max-width: 420px; }}
  .k {{ font: 11px/1 ui-monospace, monospace; letter-spacing: .15em; color: #FF9A88; }}
  h1 {{ font: 500 30px/1.15 Georgia, serif; margin: 12px 0; }}
  p {{ color: #A3A09A; }}
  code {{ color: #F2EFE9; }}
</style></head>
<body><main><div class="k">{kicker}</div><h1>{title}</h1><p>{body}</p></main></body></html>"""


def _page(status: int, kicker: str, title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        _PAGE.format(kicker=kicker, title=html.escape(title), body=body),
        status_code=status,
        headers={
            **_HEADERS,
            "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )


def _with_utm(url: str) -> str:
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if any(k == "utm_source" for k, _ in query):
        return url
    query += [("utm_source", "wearx"), ("utm_medium", "social")]
    return urlunsplit(parts._replace(query=urlencode(query)))


@router.get(
    "/r/{token}",
    response_class=Response,
    include_in_schema=False,
    dependencies=[Depends(rate_limit("go", 120, 60, by="ip"))],
)
async def go(token: str, session: Session) -> Response:
    parsed = parse_go_token(token)
    if parsed is None:
        return _page(404, "LINK", "Link non valido", "Questo indirizzo non porta a nessun negozio.")
    link_id, post_id, item = parsed
    row = (
        (
            await session.execute(
                text(
                    """select l.url, l.final_url, l.domain, l.status::text as status,
                              exists (select 1 from app.business_domains bd
                                        join app.posts p on p.id = :post
                                       where bd.user_id = p.author_id
                                         and bd.verified_at is not null
                                         and (l.domain = bd.domain
                                              or l.domain like '%.' || bd.domain)) as verified,
                              exists (select 1 from app.post_items i
                                       where i.post_id = :post and i.position = :item
                                         and i.link_id = l.id) as belongs
                         from app.links l where l.id = :id"""
                ),
                {"id": link_id, "post": post_id, "item": item},
            )
        )
        .mappings()
        .first()
    )
    if row is None or not row["belongs"]:
        return _page(
            404,
            "LINK",
            "Link non più disponibile",
            "Il capo è stato modificato o il fit non c'è più.",
        )
    if row["status"] == "blocked":
        return _page(
            451,
            "LINK BLOCCATO",
            "Abbiamo fermato questo link",
            f"Il sito <code>{html.escape(row['domain'])}</code> è stato segnalato come pericoloso "
            "(truffe, phishing o malware). Per sicurezza non ti ci portiamo.",
        )
    await session.execute(
        text("update app.links set clicks = clicks + 1 where id = :id"), {"id": link_id}
    )
    await session.execute(
        text("update app.post_stats set shop_clicks = shop_clicks + 1 where post_id = :post"),
        {"post": post_id},
    )
    await session.commit()
    target = row["url"]
    if row["verified"]:
        target = _with_utm(target)
    return RedirectResponse(target, status_code=302, headers=_HEADERS)
