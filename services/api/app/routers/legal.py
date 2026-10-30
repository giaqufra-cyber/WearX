"""Pagine legali (seduta 24): Termini, Privacy, Regole della community, Come funziona il feed.

I testi stanno in `app/legal/*.md` (facili da far rivedere e correggere) e qui diventano pagine
HTML semplici, leggibili sul telefono, senza script e senza risorse esterne. L'app le apre dai
link che riceve in `/v1/config` (legal.*). Quando ci sarà il sito wearx.app basterà impostare
WEARX_LEGAL_BASE_URL e copiare lì le stesse pagine.
"""

from __future__ import annotations

import base64
import hashlib
import html
import re
from functools import cache
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.errors import ApiError
from app.i18n import N_, Lang, tr

router = APIRouter(tags=["legal"], include_in_schema=False)

LEGAL_DIR = Path(__file__).resolve().parent.parent / "legal"
PAGES = {
    "termini": N_("Termini di servizio"),
    "privacy": N_("Informativa privacy"),
    "regole": N_("Regole della community"),
    "come-funziona-il-feed": N_("Come funziona il feed"),
    "cancellazione-account": N_("Cancellare l'account"),
}

STYLE = """
:root{color-scheme:dark}
body{margin:0;background:#0B0B0C;color:#F2F2F0;font:16px/1.6 -apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:720px;margin:0 auto;padding:24px 20px 64px}
h1{font-size:30px;line-height:1.2;margin:8px 0 4px}
h2{font-size:20px;margin:32px 0 8px}
p,li{color:#D6D6D2}
a{color:#D4FF3A}
strong{color:#F2F2F0}
.version{color:#A1A19B;font-size:14px;margin:0 0 24px}
.draft{border:1px solid #D4FF3A;border-radius:12px;padding:12px 14px;color:#F2F2F0;margin:0 0 20px}
.table{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border-bottom:1px solid #2A2A2E;padding:8px 6px;text-align:left;vertical-align:top}
th{color:#F2F2F0}
nav{margin-top:40px;padding-top:16px;border-top:1px solid #2A2A2E;font-size:14px}
nav a{margin-right:16px;display:inline-block;padding:6px 0}
"""
STYLE_HASH = base64.b64encode(hashlib.sha256(STYLE.encode()).digest()).decode()
CSP = (
    f"default-src 'none'; style-src 'sha256-{STYLE_HASH}'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)

_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _inline(raw: str) -> str:
    out = html.escape(raw, quote=True)
    out = _BOLD.sub(r"<strong>\1</strong>", out)

    def link(m: re.Match[str]) -> str:
        href = m.group(2)
        # Solo pagine sorelle (es. "privacy") o indirizzi https: niente javascript: e simili.
        if not (re.fullmatch(r"[a-z0-9-]+", href) or href.startswith("https://")):
            return m.group(1)
        return f'<a href="{href}">{m.group(1)}</a>'

    return _LINK.sub(link, out)


def render_markdown(source: str) -> str:
    """Il Markdown dei testi legali: titoli, paragrafi, elenchi, tabelle, grassetto, link."""
    blocks: list[str] = []
    para: list[str] = []
    items: list[str] = []
    ordered = False
    rows: list[list[str]] = []

    def flush() -> None:
        nonlocal para, items, rows
        if para:
            blocks.append(f"<p>{_inline(' '.join(para))}</p>")
            para = []
        if items:
            tag = "ol" if ordered else "ul"
            blocks.append(
                f"<{tag}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{tag}>"
            )
            items = []
        if rows:
            head, *body = rows
            cells = "".join(f"<th>{_inline(c)}</th>" for c in head)
            trs = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body
            )
            blocks.append(
                f'<div class="table"><table><thead><tr>{cells}</tr></thead>'
                f"<tbody>{trs}</tbody></table></div>"
            )
            rows = []

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
        elif stripped.startswith("|"):
            if para or items:
                flush()
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                rows.append(cells)
        elif m := re.match(r"(#{1,3}) (.*)", stripped):
            flush()
            level = len(m.group(1))
            blocks.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
        elif m := re.match(r"(-|\d+\.) (.*)", stripped):
            if para or rows:
                flush()
            ordered = m.group(1) != "-"
            items.append(m.group(2))
        elif items and line.startswith("  "):
            items[-1] += " " + stripped  # continuazione della voce di elenco
        else:
            if items or rows:
                flush()
            para.append(stripped)
    flush()
    return "\n".join(blocks)


@cache
def _page(slug: str, draft: bool, lang: Lang) -> str:
    # In inglese le stesse pagine stanno in legal/en/ (seduta 34); fa fede l'italiano.
    folder = LEGAL_DIR / "en" if lang == "en" else LEGAL_DIR
    source = (folder / f"{slug}.md").read_text(encoding="utf-8")
    body = render_markdown(source)
    # La riga sotto il titolo ("Versione ..." / "Version ...") in grigio.
    body = re.sub(
        r"</h1>\n<p>(Versione? [^<]*)</p>", r'</h1>\n<p class="version">\1</p>', body, count=1
    )
    banner = (
        '<p class="draft" role="note"><strong>'
        + html.escape(tr("Bozza.", lang))
        + "</strong> "
        + html.escape(
            tr(
                "Testo da far rivedere a un legale prima del lancio: le parti tra parentesi "
                "quadre vanno completate.",
                lang,
            )
        )
        + "</p>"
        if draft
        else ""
    )
    nav = "".join(
        f'<a href="{s}">{html.escape(tr(t, lang))}</a>' for s, t in PAGES.items() if s != slug
    )
    others = html.escape(tr("Altri documenti", lang), quote=True)
    return (
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(tr(PAGES[slug], lang))} · WearX</title>"
        f"<style>{STYLE}</style></head>"
        f'<body><main>{banner}{body}<nav aria-label="{others}">{nav}</nav>'
        "</main></body></html>"
    )


def _response(slug: str, lang: Lang) -> HTMLResponse:
    if slug not in PAGES:
        raise ApiError(404, "legal.not_found", "Pagina non trovata")
    return HTMLResponse(
        _page(slug, get_settings().legal_draft, lang),
        headers={"Cache-Control": "public, max-age=3600", "Content-Security-Policy": CSP},
    )


@router.get("/legal/{slug}", response_class=HTMLResponse)
async def legal_page(slug: str) -> HTMLResponse:
    return _response(slug, "it")


@router.get("/legal/en/{slug}", response_class=HTMLResponse)
async def legal_page_en(slug: str) -> HTMLResponse:
    return _response(slug, "en")
