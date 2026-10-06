"""Pagine legali servite dall'API (seduta 24)."""

from __future__ import annotations

import html

import pytest

from app.routers.legal import CSP, PAGES, render_markdown


@pytest.mark.parametrize("slug", list(PAGES))
async def test_pagine_legali(client, slug):
    r = await client.get(f"/legal/{slug}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["content-security-policy"] == CSP
    assert "script" not in r.text
    assert f"<title>{html.escape(PAGES[slug])} · WearX</title>" in r.text
    assert "<strong>Bozza.</strong>" in r.text  # finché non lo rivede un legale
    assert r.text.count("<h1>") == 1


async def test_pagina_che_non_esiste(client):
    r = await client.get("/legal/segreti")
    assert r.status_code == 404


async def test_la_configurazione_punta_alle_pagine(client):
    legal = (await client.get("/v1/config")).json()["legal"]
    assert legal["privacy"].endswith("/legal/privacy")
    r = await client.get(legal["feed_explainer"].split("8000", 1)[-1])
    assert r.status_code == 200


def test_markdown_sicuro():
    out = render_markdown(
        "# Titolo\n\nTesto con **grassetto**, [link](regole), [cattivo](javascript:alert(1)) "
        "e <script>x</script>.\n\n- uno\n  continua\n- due\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    )
    assert "<h1>Titolo</h1>" in out
    assert '<a href="regole">link</a>' in out
    assert "javascript" not in out and "<script>" not in out
    assert "<li>uno continua</li>" in out
    assert "<th>A</th>" in out and "<td>2</td>" in out
